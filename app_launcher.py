#!/usr/bin/env python3
"""
Interactive Standalone App Launcher for AI Web Form Testing Framework.

Run directly via:
    python3 app_launcher.py
No IDE required. Prompts for target form URL and testing mode, executes the
testing engine, and launches the browser dashboard.
"""
import os
import sys
import subprocess

TARGET_PYTHON = "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
if os.path.exists(TARGET_PYTHON) and sys.executable != TARGET_PYTHON:
    os.execv(TARGET_PYTHON, [TARGET_PYTHON] + sys.argv)

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "ai-form-test-framework"))
from framework_api import test_web_form


def main():
    print("=" * 80)
    print("   AI-BASED WEB FORM TESTING FRAMEWORK - APPLICATION LAUNCHER")
    print("=" * 80)
    print("Autonomous Testing · Accessibility Tree · DOM Extraction · Pytest Contract")
    print("=" * 80)

    # 1. URL Prompt
    url = input("\n👉 Enter the Web Form URL to test (e.g. https://example.com/login):\n> ").strip()
    while not url.startswith("http://") and not url.startswith("https://"):
        print("❌ Invalid URL. Please include http:// or https:// (e.g. https://example.com/form)")
        url = input("> ").strip()

    # 2. Mode Prompt
    print("\n👉 Choose Requirements Specification Mode:")
    print("  [1] Case B: Black-Box Testing (Chromium Accessibility Tree + DOM Features) [Default]")
    print("  [2] Case A: Specification-Driven Testing (SRS Document)")
    choice = input("Enter 1 or 2 [default: 1]: ").strip()

    srs_path = None
    blackbox = True
    if choice == "2":
        blackbox = False
        default_srs = os.path.join(ROOT, "ai-form-test-framework", "srs", "registration_srs.md")
        srs_in = input(f"Enter SRS file path (.md/.txt) [press Enter for '{os.path.basename(default_srs)}']:\n> ").strip()
        srs_path = srs_in if srs_in else default_srs

    print("\n" + "-" * 80)
    print(f"🚀 Running test suite against: {url}")
    print(f"📋 Mode: {'Black-Box (Accessibility + DOM)' if blackbox else f'Specification ({srs_path})'}")
    print("-" * 80)

    # Run tests
    res = test_web_form(
        target_url=url,
        srs_path=srs_path,
        blackbox=blackbox,
        run_tests=True,
    )

    print("\n" + res["error_log_content"])
    print(f"\n[INFO] Detailed error log saved to: {res['error_log_path']}")

    # Open dashboard prompt
    open_dash = input("\n👉 Open the Quality Intelligence Dashboard in your browser? [Y/n]: ").strip().lower()
    if open_dash != "n":
        print("Launching dashboard on http://localhost:8501 ...")
        dash_script = os.path.join(ROOT, "ai-form-test-framework", "dashboard", "streamlit_app.py")
        subprocess.run([sys.executable, "-m", "streamlit", "run", dash_script])


if __name__ == "__main__":
    main()
