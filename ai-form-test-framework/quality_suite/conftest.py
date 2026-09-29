"""
Pytest plugin for the quality suite.

1. Plain-English test catalog
   Tests declare intent with a docstring plus
       @pytest.mark.description(intent="...", fields=["age"], expected="...")
   pytest_collection_modifyitems harvests these into the `catalog` table so
   the dashboard can show a readable catalog even for tests that have not run.

2. Failure artifact capture (pytest_runtest_makereport hook)
   On every test outcome we store the result; on failure we also capture
   stack trace, HTTP trace/status, browser console output and a Playwright
   screenshot, then ask the LLM layer (rca.py) for a 2-sentence diagnosis.

3. Everything is written to SQLite (results/quality.db) for Streamlit.
"""
import os
import sys
import time
from collections import Counter

import pytest
import requests

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)

import db  # noqa: E402
from rca import diagnose  # noqa: E402

RESULTS_DIR = os.path.abspath(os.path.join(HERE, "..", "results"))
SHOT_DIR = os.path.join(RESULTS_DIR, "failure_screenshots")

_STATE = {"run_id": None, "counts": Counter(), "start": 0.0}

# Deliberately failing demo tests are only collected on request.
collect_ignore = [] if os.environ.get("QS_DEMO_FAILURES") == "1" else ["test_demo_failures.py"]


def _layer_for(item) -> str:
    fname = os.path.basename(str(item.fspath))
    fixtures = getattr(item, "fixturenames", [])
    if fname.startswith("test_visual"):
        return "visual"
    if "page" in fixtures:
        return "functional"
    if "api" in fixtures or fname.startswith("test_api"):
        return "unit/contract"
    return "functional"


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


# --------------------------------------------------------------------------
# Session lifecycle
# --------------------------------------------------------------------------
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "description(intent, fields, expected): plain-English test intent, "
        "target form fields and expected outcome, shown in the dashboard catalog",
    )


def pytest_sessionstart(session):
    db.init()
    _STATE["run_id"] = db.create_run(os.environ.get("QS_CASE_MODE", "n/a"))
    _STATE["start"] = time.time()
    _STATE["counts"] = Counter()
    os.makedirs(SHOT_DIR, exist_ok=True)


def pytest_sessionfinish(session, exitstatus):
    c = _STATE["counts"]
    total = sum(c.values())
    db.finish_run(_STATE["run_id"], total, c["passed"], c["failed"], c["skipped"],
                  round(time.time() - _STATE["start"], 2))


def pytest_collection_modifyitems(session, config, items):
    rows = []
    for it in items:
        d = _description(it)
        rows.append({
            "nodeid": it.nodeid, "name": it.name, "layer": _layer_for(it),
            "intent": d["intent"], "target_fields": d["target_fields"],
            "expected": d["expected"], "docstring": _doc(it),
        })
    if rows:
        db.replace_catalog(rows)


# --------------------------------------------------------------------------
# Trace fixtures: browser console + HTTP traffic, for failure context
# --------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _trace(request):
    trace = {"console": [], "http": []}
    request.node._trace = trace
    if "page" in request.fixturenames:
        page = request.getfixturevalue("page")
        page.on("console", lambda m: trace["console"].append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: trace["console"].append(f"[pageerror] {e}"))
        page.on("response", lambda r: trace["http"].append(f"{r.request.method} {r.url} -> {r.status}"))
    yield


@pytest.fixture
def api(request, base_url):
    """requests wrapper that records every call into the failure trace."""
    trace = request.node._trace

    class Client:
        def _do(self, method, path, **kw):
            r = requests.request(method, base_url.rstrip("/") + path, timeout=10, **kw)
            trace["http"].append(f"{method} {path} -> {r.status_code}")
            return r

        def get(self, path, **kw):
            return self._do("GET", path, **kw)

        def post(self, path, **kw):
            return self._do("POST", path, **kw)

    return Client()


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    # Fixed viewport => deterministic screenshots for visual regression.
    return {**browser_context_args, "viewport": {"width": 1280, "height": 800}}


# --------------------------------------------------------------------------
# The hook: record every outcome, enrich failures, ask the LLM why
# --------------------------------------------------------------------------
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

    trace = getattr(item, "_trace", {"console": [], "http": []})
    d = _description(item)
    row = dict(
        nodeid=item.nodeid, name=item.name, layer=_layer_for(item), outcome=status,
        duration_s=round(rep.duration, 3), intent=d["intent"],
        target_fields=d["target_fields"], expected=d["expected"], docstring=_doc(item),
        error="", stack="", http_status=None,
        http_trace="\n".join(trace["http"][-8:]), console_logs="\n".join(trace["console"][-10:]),
        screenshot=None, diagnosis=None, diagnosis_provider=None,
    )

    # last HTTP status seen, useful context for both UI and API tests
    for line in reversed(trace["http"]):
        if "->" in line:
            try:
                row["http_status"] = int(line.rsplit("->", 1)[1].strip())
                break
            except ValueError:
                pass

    if rep.failed:
        row["error"] = call.excinfo.exconly() if call.excinfo else str(rep.longrepr)[:500]
        row["stack"] = rep.longreprtext[-4000:]

        page = item.funcargs.get("page") if hasattr(item, "funcargs") else None
        if page is not None:
            try:
                path = os.path.join(SHOT_DIR, f"run{_STATE['run_id']}_{item.name}.png")
                page.screenshot(path=path)
                row["screenshot"] = os.path.relpath(path, os.path.join(HERE, ".."))
            except Exception:
                pass

        text, provider = diagnose(row)
        row["diagnosis"], row["diagnosis_provider"] = text, provider

    db.add_result(_STATE["run_id"], **row)
