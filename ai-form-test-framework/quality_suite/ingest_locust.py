"""
Ingest Locust's CSV output (results/locust_api_*.csv) into the SQLite DB,
attached to the most recent pytest run, so Streamlit can show performance
alongside functional results.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import db  # noqa: E402

RESULTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "results"))


def _f(row, key, default=0.0):
    try:
        return float(row.get(key) or default)
    except ValueError:
        return default


def ingest(run_id=None):
    db.init()
    run_id = run_id or db.latest_run_id()
    if run_id is None:
        print("[ingest_locust] No run found; run pytest first.")
        return

    stats = os.path.join(RESULTS, "locust_api_stats.csv")
    if os.path.exists(stats):
        with open(stats, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if not row.get("Name"):
                    continue
                db.add_perf_stat(
                    run_id, row["Name"], int(_f(row, "Request Count")), int(_f(row, "Failure Count")),
                    _f(row, "Median Response Time"), _f(row, "Average Response Time"),
                    _f(row, "95%"), _f(row, "Requests/s"),
                )

    hist = os.path.join(RESULTS, "locust_api_stats_history.csv")
    n = 0
    if os.path.exists(hist):
        with open(hist, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("Name") != "Aggregated":
                    continue
                db.add_perf_point(
                    run_id, row.get("Timestamp"), int(_f(row, "User Count")),
                    _f(row, "Requests/s"), _f(row, "95%"), _f(row, "Failures/s"),
                )
                n += 1
    print(f"[ingest_locust] run {run_id}: stats + {n} time-series points ingested.")


if __name__ == "__main__":
    ingest(int(sys.argv[1]) if len(sys.argv) > 1 else None)
