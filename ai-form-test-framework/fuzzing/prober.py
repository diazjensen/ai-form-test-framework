"""
CASE B: Backend code NOT available.
Black-box probing engine. For each field discovered by extract_dom.py,
submits a battery of boundary/invalid inputs directly to the submit
endpoint and clusters the responses to INFER constraints, with a simple
confidence score per inferred rule.

This is the "AI/heuristic" component for the no-backend path: a rule-based
classifier over response patterns (status code + error text presence).
A small ML classifier could replace the heuristics below as future work.
"""
import json
import os
import sys
import urllib.parse
import requests

SUBMIT_URL = "http://127.0.0.1:5000/submit"

def get_submit_url():
    global SUBMIT_URL
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        return sys.argv[1]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dom_path = os.path.join(root, "results", "dom_features.json")
    if os.path.exists(dom_path):
        try:
            with open(dom_path, encoding="utf-8") as f:
                dom = json.load(f)
            src = dom.get("source_url", "http://127.0.0.1:5000/")
            endpoint = dom.get("submit_endpoint", "/submit")
            return urllib.parse.urljoin(src, endpoint)
        except Exception:
            pass
    return SUBMIT_URL

# Baseline valid values used to fill every OTHER field while probing one
# field at a time (so failures can be attributed to the field under test).
VALID_BASELINE = {
    "full_name": "Jane Doe",
    "email": "jane.doe@example.com",
    "age": "25",
    "password": "SecurePass1",
    "phone": "9876543210",
}

# Generic probe values applied to every field regardless of declared type.
GENERIC_PROBES = {
    "empty": "",
    "single_char": "a",
    "very_long": "x" * 300,
    "sql_injection": "' OR '1'='1",
    "script_tag": "<script>alert(1)</script>",
    "non_numeric": "abc123",
}

_session = None

def get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
        _session.mount("https://", adapter)
        _session.mount("http://", adapter)
    return _session


def submit(payload: dict, target_url: str = None):
    url = target_url or get_submit_url()
    s = get_session()
    try:
        r = s.post(url, data=payload, timeout=8, allow_redirects=True)
        return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    except Exception as e:
        return None, {"exception": str(e)}


def infer_field_constraints(field_name: str, baseline: dict = None) -> dict:
    inferred = {"required": False, "notes": [], "confidence": {}}
    base = dict(baseline if baseline is not None else VALID_BASELINE)

    for probe_name, probe_value in GENERIC_PROBES.items():
        payload = dict(base)
        payload[field_name] = probe_value
        status, body = submit(payload)
        rejected = status == 400
        error_text = (body.get("errors", {}) or {}).get(field_name, "")

        if probe_name == "empty" and rejected:
            inferred["required"] = True
            inferred["confidence"]["required"] = 0.95

        if probe_name == "very_long" and rejected and "characters" in error_text:
            inferred["max_len_suspected"] = True
            inferred["confidence"]["max_len"] = 0.7

        if probe_name == "single_char" and rejected and "characters" in error_text:
            inferred["min_len_suspected"] = True
            inferred["confidence"]["min_len"] = 0.6

        if probe_name == "non_numeric" and rejected and "number" in error_text:
            inferred["type_suspected"] = "number"
            inferred["confidence"]["type"] = 0.8

        if probe_name in ("sql_injection", "script_tag") and not rejected:
            inferred["notes"].append(
                f"Field accepted potentially unsafe input via '{probe_name}' probe "
                "(no server-side sanitisation observed)."
            )

        if probe_name == "negative_number" and rejected and "must be >=" in error_text:
            inferred["min_value_suspected"] = True
            inferred["confidence"]["min_value"] = 0.75

        if probe_name == "huge_number" and rejected and "must be <=" in error_text:
            inferred["max_value_suspected"] = True
            inferred["confidence"]["max_value"] = 0.75

    return inferred


def run_probing(field_names) -> dict:
    results = {"source": "black_box_fuzzing", "fields": {}}
    baseline = dict(VALID_BASELINE)
    for name in field_names:
        if name not in baseline:
            baseline[name] = "test_val"

    for name in field_names:
        results["fields"][name] = infer_field_constraints(name, baseline=baseline)
    return results


if __name__ == "__main__":
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dom_path = os.path.join(root, "results", "dom_features.json")
    with open(dom_path, encoding="utf-8") as f:
        dom = json.load(f)
    field_names = [f["name"] for f in dom["fields"]]

    data = run_probing(field_names)
    out_path = os.path.join(root, "results", "inferred_rules.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Probed {len(field_names)} fields -> {out_path}")
