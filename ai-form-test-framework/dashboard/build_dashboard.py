"""
Aggregates results/*.json (Playwright, pytest, Locust CSV stats) into one
unified HTML dashboard: pass/fail counts per layer, inferred-constraint
confidence (Case B), and performance metrics (RPS, latency, failure rate).
"""
import json
import os
import csv

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
OUT_PATH = os.path.join(os.path.dirname(__file__), "dashboard.html")


def safe_load_json(name):
    path = os.path.join(RESULTS_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_locust_stats():
    path = os.path.join(RESULTS_DIR, "locust_stats.csv")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        if row.get("Name") == "Aggregated":
            return row
    return rows[-1] if rows else None


def build():
    case_model = safe_load_json("feature_model_caseA.json") or safe_load_json("feature_model_caseB.json")
    pw_results = safe_load_json("playwright_results.json") or []
    pytest_results = safe_load_json("pytest_results.json") or {}
    locust_row = load_locust_stats()

    pw_passed = sum(1 for r in pw_results if r["passed"])
    pw_total = len(pw_results)

    pt_passed = pytest_results.get("passed", 0)
    pt_total = pytest_results.get("total", 0)

    case_label = case_model["case"] if case_model else "N/A"
    backend_meta = safe_load_json("backend_rules.json")
    if case_label == "A" and backend_meta:
        source_label = f"Backend reference: <code>{backend_meta.get('reference_path')}</code>"
    else:
        source_label = "Black-box inference (fuzzing) — no backend reference supplied"

    field_rows = ""
    if case_model:
        for f in case_model["fields"]:
            conf = f.get("confidence", 1.0)
            conf_pct = f"{conf*100:.0f}%"
            color = "#16a34a" if conf >= 0.8 else ("#d97706" if conf >= 0.5 else "#dc2626")
            field_rows += f"""
            <tr>
              <td>{f['name']}</td><td>{f['type']}</td><td>{f['required']}</td>
              <td>{f['source']}</td>
              <td><span style="color:{color};font-weight:600">{conf_pct}</span></td>
            </tr>"""

    pw_rows = "".join(
        f"<tr><td>{r['test']}</td><td style='color:{"#16a34a" if r["passed"] else "#dc2626"}'>"
        f"{'PASS' if r['passed'] else 'FAIL'}</td><td>{r.get('detail','')}</td></tr>"
        for r in pw_results
    )

    locust_block = "<p>No Locust run data found. Run <code>locust -f tests_generated/locustfile.py --headless -u 20 -r 5 -t 30s --csv=results/locust</code> first.</p>"
    if locust_row:
        locust_block = f"""
        <div class="metrics">
          <div class="metric"><span>{locust_row.get('Request Count','-')}</span><label>Total Requests</label></div>
          <div class="metric"><span>{locust_row.get('Failure Count','-')}</span><label>Failures</label></div>
          <div class="metric"><span>{locust_row.get('Median Response Time','-')} ms</span><label>Median Latency</label></div>
          <div class="metric"><span>{locust_row.get('Average Response Time','-')} ms</span><label>Avg Latency</label></div>
          <div class="metric"><span>{locust_row.get('Requests/s','-')}</span><label>Requests/sec</label></div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI Web-Form Testing Framework — Dashboard</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background:#0f172a; color:#e2e8f0; margin:0; padding:2rem; }}
  h1 {{ color:#38bdf8; }}
  .badge {{ display:inline-block; padding:.25rem .75rem; border-radius:999px; background:#1e293b; color:#94a3b8; font-size:.8rem; margin-left:.5rem; }}
  section {{ background:#1e293b; border-radius:14px; padding:1.5rem; margin-top:1.5rem; box-shadow:0 10px 30px rgba(0,0,0,.3); }}
  h2 {{ margin-top:0; color:#f1f5f9; border-bottom:1px solid #334155; padding-bottom:.5rem; }}
  table {{ width:100%; border-collapse:collapse; margin-top:1rem; }}
  th, td {{ text-align:left; padding:.5rem .75rem; border-bottom:1px solid #334155; font-size:.9rem; }}
  th {{ color:#94a3b8; text-transform:uppercase; font-size:.75rem; letter-spacing:.05em; }}
  .summary {{ display:flex; gap:1.5rem; flex-wrap:wrap; }}
  .card {{ background:#0f172a; border-radius:10px; padding:1rem 1.5rem; flex:1; min-width:160px; text-align:center; }}
  .card span {{ display:block; font-size:2rem; font-weight:700; color:#38bdf8; }}
  .card label {{ font-size:.8rem; color:#94a3b8; }}
  .metrics {{ display:flex; gap:1.5rem; flex-wrap:wrap; margin-top:1rem; }}
  .metric {{ background:#0f172a; border-radius:10px; padding:1rem 1.5rem; flex:1; min-width:140px; text-align:center; }}
  .metric span {{ display:block; font-size:1.5rem; font-weight:700; color:#f59e0b; }}
  .metric label {{ font-size:.75rem; color:#94a3b8; }}
</style>
</head>
<body>
  <h1>AI-Based Web-Form Testing Framework <span class="badge">Case {case_label}: {source_label}</span></h1>

  <section>
    <h2>Overview</h2>
    <div class="summary">
      <div class="card"><span>{pw_passed}/{pw_total}</span><label>Playwright (Functional)</label></div>
      <div class="card"><span>{pt_passed}/{pt_total}</span><label>PyTest (Contract/Unit)</label></div>
      <div class="card"><span>{len(case_model['fields']) if case_model else 0}</span><label>Fields Analyzed</label></div>
    </div>
  </section>

  <section>
    <h2>Extracted / Inferred Field Model</h2>
    <table>
      <tr><th>Field</th><th>Type</th><th>Required</th><th>Source</th><th>Confidence</th></tr>
      {field_rows}
    </table>
  </section>

  <section>
    <h2>Functional Test Results (Playwright)</h2>
    <table>
      <tr><th>Test</th><th>Result</th><th>Detail</th></tr>
      {pw_rows}
    </table>
  </section>

  <section>
    <h2>Performance Metrics (Locust)</h2>
    {locust_block}
  </section>
</body>
</html>
"""
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard built -> {OUT_PATH}")


if __name__ == "__main__":
    build()
