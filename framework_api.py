"""
Root-level import proxy for framework_api.
Allows importing test_web_form directly from the workspace root.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMEWORK_DIR = os.path.join(HERE, "ai-form-test-framework")
sys.path.insert(0, FRAMEWORK_DIR)

from framework_api import test_web_form, DEFAULT_ERROR_LOG, DEFAULT_ERROR_JSON  # noqa: E402, F401

if __name__ == "__main__":
    TARGET_PYTHON = "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
    if os.path.exists(TARGET_PYTHON) and sys.executable != TARGET_PYTHON:
        os.execv(TARGET_PYTHON, [TARGET_PYTHON] + sys.argv)

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
