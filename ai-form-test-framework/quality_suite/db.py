"""
SQLite persistence for the Quality Intelligence Dashboard.

Pytest (via conftest.py hooks) writes every run, every test result, the
plain-English test catalog and LLM diagnoses here; Locust results are
ingested afterwards; Streamlit reads it all back. One file, no server:
results/quality.db
"""
import os
import sqlite3
import time

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "results", "quality.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT, finished_at TEXT, case_mode TEXT,
    total INTEGER DEFAULT 0, passed INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0, skipped INTEGER DEFAULT 0,
    duration_s REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER, nodeid TEXT, name TEXT, layer TEXT, outcome TEXT,
    duration_s REAL, intent TEXT, target_fields TEXT, expected TEXT,
    docstring TEXT, error TEXT, stack TEXT, http_status INTEGER,
    http_trace TEXT, console_logs TEXT, screenshot TEXT, diagnosis TEXT,
    diagnosis_provider TEXT
);
CREATE TABLE IF NOT EXISTS catalog (
    nodeid TEXT PRIMARY KEY, name TEXT, layer TEXT, intent TEXT,
    target_fields TEXT, expected TEXT, docstring TEXT
);
CREATE TABLE IF NOT EXISTS perf_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, endpoint TEXT,
    requests INTEGER, failures INTEGER, median_ms REAL, avg_ms REAL,
    p95_ms REAL, rps REAL
);
CREATE TABLE IF NOT EXISTS perf_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER, ts TEXT,
    users INTEGER, rps REAL, p95_ms REAL, failures_per_s REAL
);
"""


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init():
    with connect() as c:
        c.executescript(SCHEMA)


def create_run(case_mode="n/a") -> int:
    with connect() as c:
        cur = c.execute(
            "INSERT INTO runs (started_at, case_mode) VALUES (?, ?)",
            (time.strftime("%Y-%m-%d %H:%M:%S"), case_mode),
        )
        return cur.lastrowid


def finish_run(run_id, total, passed, failed, skipped, duration_s):
    with connect() as c:
        c.execute(
            "UPDATE runs SET finished_at=?, total=?, passed=?, failed=?, skipped=?, duration_s=? WHERE id=?",
            (time.strftime("%Y-%m-%d %H:%M:%S"), total, passed, failed, skipped, duration_s, run_id),
        )


def add_result(run_id, **f):
    cols = ["run_id"] + list(f.keys())
    with connect() as c:
        c.execute(
            f"INSERT INTO test_results ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
            [run_id] + list(f.values()),
        )


def replace_catalog(rows):
    with connect() as c:
        c.execute("DELETE FROM catalog")
        c.executemany(
            "INSERT OR REPLACE INTO catalog (nodeid,name,layer,intent,target_fields,expected,docstring) "
            "VALUES (:nodeid,:name,:layer,:intent,:target_fields,:expected,:docstring)",
            rows,
        )


def latest_run_id():
    with connect() as c:
        row = c.execute("SELECT MAX(id) AS m FROM runs").fetchone()
        return row["m"]


def add_perf_stat(run_id, endpoint, requests, failures, median_ms, avg_ms, p95_ms, rps):
    with connect() as c:
        c.execute(
            "INSERT INTO perf_stats (run_id,endpoint,requests,failures,median_ms,avg_ms,p95_ms,rps) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (run_id, endpoint, requests, failures, median_ms, avg_ms, p95_ms, rps),
        )


def add_perf_point(run_id, ts, users, rps, p95_ms, failures_per_s):
    with connect() as c:
        c.execute(
            "INSERT INTO perf_history (run_id,ts,users,rps,p95_ms,failures_per_s) VALUES (?,?,?,?,?,?)",
            (run_id, ts, users, rps, p95_ms, failures_per_s),
        )
