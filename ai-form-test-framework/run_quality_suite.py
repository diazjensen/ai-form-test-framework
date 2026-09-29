"""
Runs the whole quality suite and populates the Streamlit dashboard's database.

    py run_quality_suite.py            # pytest + 30s Locust load test + ingest
    py run_quality_suite.py --no-load  # skip Locust (faster)
    py run_quality_suite.py --dashboard   # also launch Streamlit afterwards

Assumes the target app is already running at http://127.0.0.1:5000/.
Exit code is non-zero if any pytest test failed (so CI can gate on it);
JUnit XML is written to results/junit/pytest_quality.xml for CI reporters.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SUITE = os.path.join(ROOT, "quality_suite")
RESULTS = os.path.join(ROOT, "results")


def run(cmd, cwd):
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=cwd).returncode


def main():
    py = sys.executable
    os.makedirs(os.path.join(RESULTS, "junit"), exist_ok=True)

    pytest_rc = run([py, "-m", "pytest", "-v", "--tb=short",
                     f"--junitxml={os.path.join(RESULTS, 'junit', 'pytest_quality.xml')}"], cwd=SUITE)

    if "--no-load" not in sys.argv:
        run([py, "-m", "locust", "-f", "locustfile_api.py", "--headless",
             "-u", "20", "-r", "5", "-t", "30s",
             "--csv", os.path.join(RESULTS, "locust_api")], cwd=SUITE)
    run([py, "ingest_locust.py"], cwd=SUITE)

    print(f"\nResults stored in {os.path.join(RESULTS, 'quality.db')}")
    if "--dashboard" in sys.argv:
        run([py, "-m", "streamlit", "run", os.path.join(ROOT, "dashboard", "streamlit_app.py")], cwd=ROOT)
    else:
        print("View them with:  py -m streamlit run dashboard/streamlit_app.py")
    sys.exit(pytest_rc)


if __name__ == "__main__":
    main()
