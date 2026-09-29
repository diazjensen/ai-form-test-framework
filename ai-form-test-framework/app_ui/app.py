"""
Control-panel web app for the AI-based Web-Form Testing Framework.

Wraps the existing CLI pipeline (run_all.py) in a UI so a developer can:
  - set the target form URL
  - choose the case (auto / A / B)
  - upload or pick a backend reference file (Python VALIDATION_RULES
    dict, or a JSON-Schema file) -- this IS the "place to provide the
    backend code or reference" the framework asks for
  - run the pipeline and watch live progress
  - jump straight to the results dashboard when done

This app does not replace run_all.py / the generators -- it drives them
as a subprocess and streams their stdout, so the underlying pipeline
logic stays in one place.
"""
import os
import sys
import json
import threading
import subprocess
import time
from flask import Flask, request, jsonify, render_template, send_from_directory

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_PATH = os.path.join(ROOT, "config.json")
BACKEND_REF_DIR = os.path.join(ROOT, "backend_reference")
DASHBOARD_DIR = os.path.join(ROOT, "dashboard")

app = Flask(__name__)

# --- in-memory run state (single-run-at-a-time, fine for a student demo) ---
run_state = {
    "running": False,
    "log": [],
    "done": False,
    "success": False,
    "started_at": None,
    "finished_at": None,
}
run_lock = threading.Lock()


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


@app.route("/")
def index():
    config = load_config()
    ref_files = []
    if os.path.isdir(BACKEND_REF_DIR):
        ref_files = sorted(
            f for f in os.listdir(BACKEND_REF_DIR)
            if f.endswith((".py", ".json")) and not f.startswith("_")
        )
    return render_template("index.html", config=config, ref_files=ref_files)


@app.route("/api/config", methods=["POST"])
def api_save_config():
    data = request.get_json(force=True)
    config = load_config()
    config["target_url"] = data.get("target_url", config.get("target_url"))
    config["case"] = data.get("case", config.get("case", "auto"))
    if data.get("backend_reference_path") is not None:
        config["backend_reference_path"] = data.get("backend_reference_path")
    save_config(config)
    return jsonify({"ok": True, "config": config})


@app.route("/api/upload_reference", methods=["POST"])
def api_upload_reference():
    """Lets the developer upload their own backend reference file
    (Python VALIDATION_RULES module, or a JSON-Schema file) straight
    from the browser instead of editing config.json by hand."""
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file part"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"ok": False, "error": "No file selected"}), 400
    if not file.filename.endswith((".py", ".json")):
        return jsonify({"ok": False, "error": "Only .py or .json files are supported"}), 400

    os.makedirs(BACKEND_REF_DIR, exist_ok=True)
    dest = os.path.join(BACKEND_REF_DIR, file.filename)
    file.save(dest)

    config = load_config()
    config["backend_reference_path"] = f"backend_reference/{file.filename}"
    save_config(config)

    return jsonify({"ok": True, "saved_as": file.filename, "config": config})


def _run_pipeline_thread(forced_case):
    py = sys.executable
    cmd = [py, "run_all.py"] + ([forced_case] if forced_case in ("A", "B") else [])

    with run_lock:
        run_state.update(running=True, log=[], done=False, success=False,
                          started_at=time.strftime("%H:%M:%S"), finished_at=None)

    proc = subprocess.Popen(
        cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    for line in proc.stdout:
        with run_lock:
            run_state["log"].append(line.rstrip("\n"))
    proc.wait()

    with run_lock:
        run_state.update(
            running=False, done=True, success=(proc.returncode == 0),
            finished_at=time.strftime("%H:%M:%S"),
        )


@app.route("/api/run", methods=["POST"])
def api_run():
    with run_lock:
        if run_state["running"]:
            return jsonify({"ok": False, "error": "A run is already in progress."}), 409

    data = request.get_json(force=True) if request.data else {}
    forced_case = data.get("case_override")  # "A", "B", or None (= config.json's "case")

    thread = threading.Thread(target=_run_pipeline_thread, args=(forced_case,), daemon=True)
    thread.start()
    return jsonify({"ok": True})


@app.route("/api/status")
def api_status():
    with run_lock:
        return jsonify(dict(run_state))


@app.route("/dashboard")
def dashboard():
    return send_from_directory(DASHBOARD_DIR, "dashboard.html")


STREAMLIT_PORT = 8501


def _port_open(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


@app.route("/api/launch_dashboard", methods=["POST"])
def api_launch_dashboard():
    """Start the Streamlit Quality Intelligence Dashboard if it isn't running."""
    if not _port_open(STREAMLIT_PORT):
        subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", os.path.join(DASHBOARD_DIR, "streamlit_app.py"),
             "--server.headless", "true", "--server.port", str(STREAMLIT_PORT),
             "--browser.gatherUsageStats", "false"],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(40):
            if _port_open(STREAMLIT_PORT):
                break
            time.sleep(0.5)
    return jsonify({"ok": _port_open(STREAMLIT_PORT), "url": f"http://127.0.0.1:{STREAMLIT_PORT}"})


@app.route("/api/generate_skeleton", methods=["POST"])
def api_generate_skeleton():
    """Turn a plain-English prompt into a pytest skeleton (LLM if available,
    otherwise a deterministic template). Output lands in quality_suite/generated/."""
    prompt = (request.get_json(force=True).get("prompt") or "").strip()
    if not prompt:
        return jsonify({"ok": False, "error": "Enter a description first."}), 400
    sys.path.insert(0, os.path.join(ROOT, "quality_suite"))
    from generate_skeleton import generate
    path, provider, code = generate(prompt)
    return jsonify({"ok": True, "path": os.path.relpath(path, ROOT), "provider": provider, "code": code})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=False)
