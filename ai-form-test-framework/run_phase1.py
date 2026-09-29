"""
Phase 1 Master CLI: AI-Based Web Form Unit Testing with Pytest.

Executes the unified method `test_web_form(target_url, srs_path=...)` to:
- Accept any target web form URL (--url)
- Conditionally generate test cases:
    * With SRS document (--srs <path>): Formal specification unit tests
    * Without SRS document (--blackbox or omit --srs): Black-box testing via
      Chromium Accessibility Tree and DOM attributes
- Plain-English test cataloging (@pytest.mark.description + docstrings)
- Light LLM test skeleton generation (--prompt "...")
- Capture failure artifacts and AI root cause analysis
- Return and output a structured Error Log (results/test_errors.log)
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from framework_api import test_web_form, DEFAULT_ERROR_LOG


def main():
    parser = argparse.ArgumentParser(description="Phase 1: Pytest Unit Testing Unified Framework")
    parser.add_argument("--url", help="Target URL of the web form under test (e.g. http://127.0.0.1:5000/)")
    parser.add_argument("--srs", help="Path to Software Requirements Specification (.md/.txt)")
    parser.add_argument("--blackbox", action="store_true", help="Force black-box testing using Accessibility Tree + DOM")
    parser.add_argument("--prompt", help="Natural language prompt to generate a test skeleton using LLM")
    parser.add_argument("--demo-fail", action="store_true", help="Run intentional failure cases to demonstrate error log")
    parser.add_argument("--dashboard", action="store_true", help="Launch Streamlit dashboard afterwards")
    args = parser.parse_args()

    # Determine default URL from config if omitted
    target_url = args.url or "http://127.0.0.1:5000/"
    config_path = os.path.join(ROOT, "config.json")
    if not args.url and os.path.exists(config_path):
        try:
            import json
            with open(config_path, encoding="utf-8") as f:
                target_url = json.load(f).get("target_url", target_url)
        except Exception:
            pass

    print("=" * 80)
    print("AI-BASED WEB FORM TESTING UNIFIED FRAMEWORK - PHASE 1")
    print("=" * 80)
    print(f"Target URL   : {target_url}")
    print(f"SRS Document : {args.srs if (args.srs and not args.blackbox) else 'None (Black-Box: Accessibility Tree + DOM)'}")
    print("=" * 80)

    # Optional: LLM Test Skeleton Generation
    if args.prompt:
        print(f"\n[LLM Generator] Generating test skeleton from prompt: '{args.prompt}'...")
        py_bin = sys.executable
        py311 = "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
        if os.path.exists(py311):
            py_bin = py311
        subprocess.run([py_bin, os.path.join(ROOT, "quality_suite", "generate_skeleton.py"), args.prompt])

    # Execute the unified method
    result = test_web_form(
        target_url=target_url,
        srs_path=args.srs,
        blackbox=args.blackbox,
        run_tests=True,
        include_demo_failures=args.demo_fail,
    )

    # Display the Error Log
    print("\n" + result["error_log_content"])
    print(f"\n[INFO] Error log saved to: {result['error_log_path']}")

    if args.dashboard:
        print("\nLaunching Streamlit Quality Intelligence Dashboard...")
        py_bin = sys.executable
        py311 = "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
        if os.path.exists(py311):
            py_bin = py311
        subprocess.run([py_bin, "-m", "streamlit", "run", os.path.join(ROOT, "dashboard", "streamlit_app.py")])


if __name__ == "__main__":
    main()
