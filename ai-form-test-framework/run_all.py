"""
Orchestrator: runs the full pipeline end-to-end.

    extract (DOM) -> resolve case from config.json
         Case A: parse backend_reference_path (developer-supplied)
         Case B: black-box fuzz/infer (no reference, or reference invalid)
    -> build unified feature model -> generate Playwright/pytest/Locust
    -> run all three -> build unified dashboard

Usage:
    py run_all.py            # case decided by config.json ("case" field)
    py run_all.py A          # force Case A (errors out if the reference
                              # in config.json is missing/unusable)
    py run_all.py B          # force Case B, ignoring any reference file

Developers point the framework at their own backend reference by editing
config.json -> backend_reference_path (see backend_reference/README.md).
Leaving it blank, or setting case to "B", tests the form as a pure
black box with no backend knowledge at all.

Assumes the target app (e.g. sample_app/app.py) is already running at
config.json -> target_url in a separate terminal.
"""
import subprocess
import sys
import os
import json
import re

ROOT = os.path.dirname(__file__)


def run(cmd, cwd):
    print(f"\n$ {' '.join(cmd)}   (cwd={cwd})")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
    return result


def load_config():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def resolve_case(py, cli_override, config):
    """Decide Case A vs B, honouring config.json's 'case' field and any
    CLI override, and probing the configured backend reference when
    the mode is 'auto' or explicitly 'A'."""
    requested = (cli_override or config.get("case", "auto")).upper()

    if requested == "B":
        print("=== Case B forced: skipping backend reference entirely ===")
        return "B"

    # requested is "A" or "AUTO" -> try to load SRS document or backend reference
    sys.path.insert(0, os.path.join(ROOT, "extraction"))
    import parse_backend
    from parse_srs import get_srs_rules

    srs_path = config.get("srs_path")
    if srs_path and os.path.exists(os.path.join(ROOT, srs_path) if not os.path.isabs(srs_path) else srs_path):
        resolved_srs = os.path.join(ROOT, srs_path) if not os.path.isabs(srs_path) else srs_path
        with open(os.path.join(ROOT, "results", "dom_features.json"), encoding="utf-8") as df:
            dom_data = json.load(df)
        field_names = [f["name"] for f in dom_data.get("fields", [])]
        srs_data = get_srs_rules(resolved_srs, field_names)
        if srs_data is not None:
            print(f"=== SRS document loaded from '{srs_path}' -> running Case A ===")
            os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
            with open(os.path.join(ROOT, "results", "backend_rules.json"), "w", encoding="utf-8") as f:
                json.dump(srs_data, f, indent=2)
            return "A"

    backend_data = parse_backend.get_backend_rules()
    if backend_data is not None:
        print(f"=== Backend reference loaded from "
              f"'{backend_data['reference_path']}' -> running Case A ===")
        os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
        with open(os.path.join(ROOT, "results", "backend_rules.json"), "w", encoding="utf-8") as f:
            json.dump(backend_data, f, indent=2)
        return "A"

    if requested == "A":
        print("\n[run_all] ERROR: case is set to 'A' in config.json (or via CLI) "
              "but no usable SRS document or backend reference was found.\n"
              "Set srs_path or backend_reference_path in config.json, or set case to "
              "'auto'/'B' to test as a black box.")
        sys.exit(1)

    print("=== No usable SRS or backend reference found -> falling back to Case B (Black Box) ===")
    return "B"


def main():
    py = sys.executable
    cli_case = sys.argv[1].upper() if len(sys.argv) > 1 else None
    if cli_case:
        assert cli_case in ("A", "B"), "case argument must be A or B"

    config = load_config()

    print(f"Target: {config.get('target_url')}")

    # 1. Extract DOM features (shared; reads target_url from config.json itself)
    run([py, "extract_dom.py"], cwd=os.path.join(ROOT, "extraction"))

    # 2. Resolve case (loads/validates SRS document or backend reference if applicable)
    case = resolve_case(py, cli_case, config)

    # 3. Case-specific rule source
    if case == "B":
        print("-> Black box testing: Extracting Chromium Accessibility Tree...")
        run([py, "extract_accessibility.py", config.get("target_url", "http://127.0.0.1:5000/")],
            cwd=os.path.join(ROOT, "extraction"))
        print("-> Black box testing: Probing server boundary constraints...")
        run([py, "prober.py"], cwd=os.path.join(ROOT, "fuzzing"))

    print(f"\n=== Running pipeline for CASE {case} "
          f"({'backend reference available' if case == 'A' else 'backend NOT available'}) ===")

    # 4. Build unified feature model
    run([py, "build_feature_model.py", case], cwd=os.path.join(ROOT, "generator"))

    # 5. Generate test artifacts for all three frameworks
    run([py, "gen_playwright.py", case], cwd=os.path.join(ROOT, "generator"))
    run([py, "gen_pytest.py", case], cwd=os.path.join(ROOT, "generator"))
    run([py, "gen_locustfile.py", case], cwd=os.path.join(ROOT, "generator"))

    # 6. Run Playwright functional tests
    run([py, "test_functional.py"], cwd=os.path.join(ROOT, "tests_generated"))

    # 7. Run pytest contract/unit tests, capture pass/total
    pt = run([py, "-m", "pytest", "test_contract.py", "-v"], cwd=os.path.join(ROOT, "tests_generated"))
    summary_match = re.search(r"(\d+) passed(?:, (\d+) failed)?", pt.stdout)
    passed = int(summary_match.group(1)) if summary_match else 0
    failed = int(summary_match.group(2)) if summary_match and summary_match.group(2) else 0
    with open(os.path.join(ROOT, "results", "pytest_results.json"), "w", encoding="utf-8") as f:
        json.dump({"passed": passed, "failed": failed, "total": passed + failed}, f, indent=2)

    # 8. Run Locust headless for 30s against the live app
    run([
        py, "-m", "locust", "-f", "locustfile.py", "--headless",
        "-u", "20", "-r", "5", "-t", "30s",
        "--csv", os.path.join(ROOT, "results", "locust"),
    ], cwd=os.path.join(ROOT, "tests_generated"))

    # 9. Quality suite: markers-driven pytest (functional UI, visual, API contract),
    #    Faker-based Locust API load test, results -> SQLite for the Streamlit dashboard.
    #    Non-fatal: a failing test must not stop the legacy dashboard from building.
    os.environ["QS_CASE_MODE"] = f"Case {case}"
    run([py, "run_quality_suite.py"], cwd=ROOT)

    # 10. JUnit XML for CI (pytest's is written by the quality suite step above)
    run([py, "gen_junit.py"], cwd=os.path.join(ROOT, "dashboard"))

    # 11. Build the unified dashboard
    run([py, "build_dashboard.py"], cwd=os.path.join(ROOT, "dashboard"))

    dashboard_path = os.path.join(ROOT, "dashboard", "dashboard.html")
    print(f"\n=== DONE. Open the dashboard: {dashboard_path} ===")
    os.startfile(dashboard_path)


if __name__ == "__main__":
    main()
