"""
Unified API Method for Web Form Testing (Phase 1: Pytest Unit Testing).

Provides a programmatic function `test_web_form(target_url, srs_path=None, ...)` to:
1. Supply the URL of the web form under test.
2. Auto-generate test cases based on whether the SRS document is provided or not:
   - SRS provided: Extracts formal specification constraints (Case A).
   - SRS not provided: Conducts black box testing using the Chromium Accessibility Tree
     and Document Object Model (DOM) features + boundary probing (Case B).
3. Execute the generated Pytest suite with failure artifact capture and AI Root Cause Analysis.
4. Generate and return a structured error log detailing every error observed by the tests.
"""
import json
import os
import subprocess
import sys
import time
from typing import Dict, Any, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(ROOT, "results")
CONFIG_PATH = os.path.join(ROOT, "config.json")
DEFAULT_ERROR_LOG = os.path.join(RESULTS_DIR, "test_errors.log")
DEFAULT_ERROR_JSON = os.path.join(RESULTS_DIR, "test_errors.json")

sys.path.insert(0, os.path.join(ROOT, "extraction"))
sys.path.insert(0, os.path.join(ROOT, "generator"))
sys.path.insert(0, os.path.join(ROOT, "fuzzing"))
sys.path.insert(0, os.path.join(ROOT, "quality_suite"))


def test_web_form(
    target_url: str,
    srs_path: Optional[str] = None,
    blackbox: bool = False,
    run_tests: bool = True,
    error_log_path: Optional[str] = None,
    include_demo_failures: bool = False,
) -> Dict[str, Any]:
    """
    Main method to test a web form URL.

    Args:
        target_url: The URL of the web form under test (e.g. 'http://127.0.0.1:5000/').
        srs_path: Optional path to Software Requirements Specification (.md/.txt).
                  If None or empty, black-box testing is automatically conducted.
        blackbox: If True, forces black box mode even if an SRS path exists.
        run_tests: Whether to execute the generated test cases with Pytest.
        error_log_path: Custom path to write the error log file (defaults to results/test_errors.log).
        include_demo_failures: If True, executes intentional failure assertions to verify the error log.

    Returns:
        dict containing execution summary, generated test file path, and the errors observed.
    """
    start_time = time.time()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    log_file = error_log_path or DEFAULT_ERROR_LOG

    # Update config.json with active target
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    cfg["target_url"] = target_url
    if srs_path:
        cfg["srs_path"] = srs_path
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

    # -------------------------------------------------------------------------
    # Stage 1: DOM Feature Extraction
    # -------------------------------------------------------------------------
    from extract_dom import extract_form_features
    dom_data = extract_form_features(target_url)
    with open(os.path.join(RESULTS_DIR, "dom_features.json"), "w", encoding="utf-8") as f:
        json.dump(dom_data, f, indent=2)

    field_names = [f["name"] for f in dom_data.get("fields", [])]

    # -------------------------------------------------------------------------
    # Stage 2: Dual Mode - Check whether SRS Document is provided
    # -------------------------------------------------------------------------
    has_srs = False
    srs_resolved = None
    if srs_path and not blackbox:
        cand = os.path.join(ROOT, srs_path) if not os.path.isabs(srs_path) else srs_path
        if os.path.exists(cand):
            srs_resolved = cand
        elif os.path.exists(srs_path):
            srs_resolved = srs_path

    if srs_resolved:
        # Case A: SRS Document Provided
        from parse_srs import get_srs_rules
        srs_rules = get_srs_rules(srs_resolved, field_names)
        if srs_rules:
            with open(os.path.join(RESULTS_DIR, "backend_rules.json"), "w", encoding="utf-8") as f:
                json.dump(srs_rules, f, indent=2)
            has_srs = True
            case = "A"
            mode_desc = f"Case A: Specification-Driven (SRS: '{os.path.basename(srs_resolved)}')"

    if not has_srs:
        # Case B: No SRS Document Provided -> Conduct Black-Box Testing
        case = "B"
        mode_desc = "Case B: Black Box Testing (Chromium Accessibility Tree + DOM Features)"

        # 2a. Extract Chromium Accessibility Tree
        from extract_accessibility import extract_accessibility_tree
        ax_data = extract_accessibility_tree(target_url)
        with open(os.path.join(RESULTS_DIR, "accessibility_tree.json"), "w", encoding="utf-8") as f:
            json.dump(ax_data, f, indent=2)

        # 2b. Black-Box Probing / Fuzzing of endpoints
        from prober import run_probing
        inferred_data = run_probing(field_names)
        with open(os.path.join(RESULTS_DIR, "inferred_rules.json"), "w", encoding="utf-8") as f:
            json.dump(inferred_data, f, indent=2)

    # -------------------------------------------------------------------------
    # Stage 3: Build Unified Feature Model
    # -------------------------------------------------------------------------
    from build_feature_model import build as build_model
    feature_model = build_model(case)

    # -------------------------------------------------------------------------
    # Stage 4: Generate Pytest Unit Test Suite
    # -------------------------------------------------------------------------
    from gen_pytest import gen as generate_pytest
    test_file = generate_pytest(case)

    # -------------------------------------------------------------------------
    # Stage 5: Execute Pytest Suite & Capture Failure Artifacts
    # -------------------------------------------------------------------------
    test_results = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "duration_s": 0.0}
    observed_errors = []

    if run_tests:
        env = dict(os.environ)
        env["PHASE1_MODE"] = mode_desc
        if include_demo_failures:
            env["QS_DEMO_FAILURES"] = "1"

        tests_to_run = [test_file]
        if include_demo_failures:
            tests_to_run.append(os.path.join(ROOT, "quality_suite", "test_demo_failures.py"))

        py_bin = sys.executable
        py311 = "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
        if os.path.exists(py311):
            py_bin = py311

        import sqlite3
        db_path = os.path.join(RESULTS_DIR, "quality.db")
        max_run_before = 0
        if os.path.exists(db_path):
            try:
                with sqlite3.connect(db_path) as conn:
                    cur = conn.cursor()
                    row = cur.execute("SELECT COALESCE(MAX(id), 0) FROM runs").fetchone()
                    max_run_before = row[0] if row else 0
            except Exception:
                pass

        cmd = [py_bin, "-m", "pytest", "-v", "--tb=short"] + tests_to_run
        pt_proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)

        # Retrieve results from SQLite database for all runs generated in this session
        if os.path.exists(db_path):
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                executed_runs = conn.execute(
                    "SELECT * FROM runs WHERE id > ? ORDER BY id ASC",
                    (max_run_before,)
                ).fetchall()

                if executed_runs:
                    test_results = {
                        "run_ids": [r["id"] for r in executed_runs],
                        "total": sum(r["total"] for r in executed_runs),
                        "passed": sum(r["passed"] for r in executed_runs),
                        "failed": sum(r["failed"] for r in executed_runs),
                        "skipped": sum(r["skipped"] for r in executed_runs),
                        "duration_s": round(sum(r["duration_s"] for r in executed_runs), 2),
                    }

                    # Fetch all failure records from these runs
                    placeholders = ",".join("?" * len(executed_runs))
                    run_ids = [r["id"] for r in executed_runs]
                    failures = conn.execute(
                        f"SELECT * FROM test_results WHERE run_id IN ({placeholders}) AND outcome='failed'",
                        run_ids
                    ).fetchall()

                    for f_row in failures:
                        observed_errors.append({
                            "test_name": f_row["name"],
                            "nodeid": f_row["nodeid"],
                            "target_fields": f_row["target_fields"],
                            "intent": f_row["intent"],
                            "expected": f_row["expected"],
                            "error_message": f_row["error"],
                            "http_status": f_row["http_status"],
                            "http_trace": f_row["http_trace"],
                            "console_logs": f_row["console_logs"],
                            "screenshot": f_row["screenshot"],
                            "ai_root_cause_diagnosis": f_row["diagnosis"],
                            "ai_provider": f_row["diagnosis_provider"],
                            "stack_trace": f_row["stack"],
                        })

    # -------------------------------------------------------------------------
    # Stage 6: Build & Write Formatted Error Log
    # -------------------------------------------------------------------------
    error_log_text = _format_error_log(
        target_url=target_url,
        mode_desc=mode_desc,
        has_srs=has_srs,
        srs_path=srs_resolved,
        test_results=test_results,
        observed_errors=observed_errors,
        elapsed_s=round(time.time() - start_time, 2),
    )

    with open(log_file, "w", encoding="utf-8") as f:
        f.write(error_log_text)

    with open(DEFAULT_ERROR_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "target_url": target_url,
            "mode": mode_desc,
            "has_srs": has_srs,
            "srs_path": srs_resolved,
            "summary": test_results,
            "errors_count": len(observed_errors),
            "errors": observed_errors,
        }, f, indent=2)

    return {
        "status": "success",
        "target_url": target_url,
        "mode": mode_desc,
        "has_srs": has_srs,
        "srs_path": srs_resolved,
        "generated_test_file": test_file,
        "summary": test_results,
        "error_count": len(observed_errors),
        "errors": observed_errors,
        "error_log_path": log_file,
        "error_log_content": error_log_text,
    }


def _format_error_log(
    target_url: str,
    mode_desc: str,
    has_srs: bool,
    srs_path: Optional[str],
    test_results: dict,
    observed_errors: list,
    elapsed_s: float,
) -> str:
    sep = "=" * 80
    subsep = "-" * 80
    lines = [
        sep,
        "AI-BASED WEB FORM TESTING UNIFIED FRAMEWORK - TEST EXECUTION & ERROR LOG",
        sep,
        f"Timestamp          : {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Target URL         : {target_url}",
        f"Testing Mode       : {mode_desc}",
        f"SRS Document       : {srs_path if has_srs else 'None provided (Black-Box: Accessibility Tree + DOM used)'}",
        f"Total Tests Run    : {test_results.get('total', 0)}",
        f"Tests Passed       : {test_results.get('passed', 0)}",
        f"Tests Failed       : {test_results.get('failed', 0)}",
        f"Tests Skipped      : {test_results.get('skipped', 0)}",
        f"Execution Time     : {test_results.get('duration_s', elapsed_s)}s",
        sep,
        "",
    ]

    if not observed_errors:
        lines.extend([
            "STATUS: ALL TEST CASES PASSED SUCCESSFULLY.",
            "No functional, validation, or boundary errors observed in this test run.",
            subsep,
            "",
        ])
    else:
        lines.extend([
            f"OBSERVED ERRORS ({len(observed_errors)} test failure(s) detected):",
            subsep,
            "",
        ])
        for idx, err in enumerate(observed_errors, start=1):
            lines.extend([
                f"[FAILURE #{idx}] Test ID: {err['test_name']}",
                f"  Target Field(s)   : {err['target_fields'] or 'N/A'}",
                f"  Intent            : {err['intent'] or 'N/A'}",
                f"  Expected Outcome  : {err['expected'] or 'N/A'}",
                f"  HTTP Status Code  : {err['http_status'] or 'N/A'}",
                f"  Observed Error    : {err['error_message'].strip()}",
                "",
                f"  AI ROOT CAUSE DIAGNOSTIC (by {err['ai_provider']}):",
                f"    {err['ai_root_cause_diagnosis']}",
                "",
            ])
            if err.get("http_trace"):
                lines.extend([
                    "  Recent HTTP Trace:",
                    "    " + "\n    ".join(err["http_trace"].splitlines()[-4:]),
                    "",
                ])
            if err.get("screenshot"):
                lines.extend([
                    f"  Failure Screenshot: {err['screenshot']}",
                    "",
                ])
            if err.get("stack_trace"):
                lines.extend([
                    "  Stack Trace (tail):",
                    "    " + "\n    ".join(err["stack_trace"].splitlines()[-6:]),
                    "",
                ])
            lines.append(subsep)

    lines.extend([
        "",
        "End of Error Log.",
        sep,
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test Web Form URL via Framework API")
    parser.add_argument("url", nargs="?", default="http://127.0.0.1:5000/", help="URL of the web form under test")
    parser.add_argument("--srs", help="Path to SRS specification document")
    parser.add_argument("--blackbox", action="store_true", help="Force black-box testing")
    parser.add_argument("--demo-fail", action="store_true", help="Include intentional failing tests to verify error logging")
    args = parser.parse_args()

    result = test_web_form(
        target_url=args.url,
        srs_path=args.srs,
        blackbox=args.blackbox,
        include_demo_failures=args.demo_fail,
    )
    print(result["error_log_content"])
