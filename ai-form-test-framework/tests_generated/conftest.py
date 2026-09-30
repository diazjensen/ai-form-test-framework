"""
Pytest plugin for tests_generated/ (Phase 1 Unit / Contract Test Suite).

Features:
1. Plain-English test catalog:
   Harvests @pytest.mark.description(...) and test function docstrings into
   results/quality.db catalog table so tests are visible in Streamlit.
2. Failure artifact capture & AI-Driven Root Cause Analysis:
   Native hook pytest_runtest_makereport captures stack trace, error, and HTTP trace,
   and feeds raw failure context into lightweight LLM prompt for 2-sentence diagnostic.
3. Execution results persistence:
   Writes summary metrics to results/pytest_results.json and runs/test_results table
   in results/quality.db for the Streamlit dashboard.
"""
import os
import sys
import time
from collections import Counter
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUALITY_SUITE = os.path.join(ROOT, "quality_suite")
sys.path.insert(0, QUALITY_SUITE)

import db  # noqa: E402
from rca import diagnose  # noqa: E402

_STATE = {"run_id": None, "counts": Counter(), "start": 0.0}


def _description(item) -> dict:
    m = item.get_closest_marker("description")
    kw = dict(m.kwargs) if m else {}
    fields = kw.get("fields") or kw.get("target_fields") or kw.get("target_field") or []
    if isinstance(fields, (list, tuple)):
        fields = ", ".join(fields)
    return {
        "intent": kw.get("intent") or (m.args[0] if m and m.args else ""),
        "target_fields": str(fields),
        "expected": kw.get("expected") or kw.get("expected_outcome", ""),
    }


def _doc(item) -> str:
    fn = getattr(item, "function", None)
    return " ".join((fn.__doc__ or "").split()) if fn else ""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "description(intent, fields, expected): Plain-English test intent, target fields, and expected outcome",
    )


def pytest_sessionstart(session):
    db.init()
    mode = os.environ.get("PHASE1_MODE", os.environ.get("QS_CASE_MODE", "Phase 1: Unit Testing"))
    _STATE["run_id"] = db.create_run(mode)
    _STATE["start"] = time.time()
    _STATE["counts"] = Counter()


def pytest_sessionfinish(session, exitstatus):
    c = _STATE["counts"]
    total = sum(c.values())
    duration = round(time.time() - _STATE["start"], 2)
    db.finish_run(_STATE["run_id"], total, c["passed"], c["failed"], c["skipped"], duration)

    # Also update results/pytest_results.json
    res_path = os.path.join(ROOT, "results", "pytest_results.json")
    os.makedirs(os.path.dirname(res_path), exist_ok=True)
    import json
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump({"passed": c["passed"], "failed": c["failed"], "total": total, "duration_s": duration}, f, indent=2)


def pytest_collection_modifyitems(session, config, items):
    rows = []
    for it in items:
        d = _description(it)
        layer = "functional" if "functional" in it.nodeid.lower() else "unit/contract"
        rows.append({
            "nodeid": it.nodeid,
            "name": it.name,
            "layer": layer,
            "intent": d["intent"],
            "target_fields": d["target_fields"],
            "expected": d["expected"],
            "docstring": _doc(it),
        })
    if rows:
        db.replace_catalog(rows)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()

    is_call = rep.when == "call"
    is_setup_problem = rep.when == "setup" and (rep.failed or rep.skipped)
    if not (is_call or is_setup_problem):
        return

    status = "failed" if rep.failed else ("skipped" if rep.skipped else "passed")
    _STATE["counts"][status] += 1

    d = _description(item)
    layer = "functional" if "functional" in item.nodeid.lower() else "unit/contract"
    row = dict(
        nodeid=item.nodeid,
        name=item.name,
        layer=layer,
        outcome=status,
        duration_s=round(rep.duration, 3),
        intent=d["intent"],
        target_fields=d["target_fields"],
        expected=d["expected"],
        docstring=_doc(it := item),
        error="",
        stack="",
        http_status=None,
        http_trace="",
        console_logs="",
        screenshot=None,
        diagnosis=None,
        diagnosis_provider=None,
    )

    if rep.failed:
        row["error"] = call.excinfo.exconly() if call.excinfo else str(rep.longrepr)[:500]
        row["stack"] = rep.longreprtext[-4000:]
        text, provider = diagnose(row)
        row["diagnosis"], row["diagnosis_provider"] = text, provider

    db.add_result(_STATE["run_id"], **row)
