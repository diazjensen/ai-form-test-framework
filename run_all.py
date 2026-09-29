#!/usr/bin/env python3
"""
Master Orchestrator Launcher (End-to-End Pipeline across Pytest, Playwright, Locust).
Delegates to the Python 3.11 environment.
"""
import os
import sys

TARGET_PYTHON = "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
HERE = os.path.dirname(os.path.abspath(__file__))
FRAMEWORK_SCRIPT = os.path.join(HERE, "ai-form-test-framework", "run_all.py")

if os.path.exists(TARGET_PYTHON) and sys.executable != TARGET_PYTHON:
    os.execv(TARGET_PYTHON, [TARGET_PYTHON, FRAMEWORK_SCRIPT] + sys.argv[1:])
else:
    import subprocess
    sys.exit(subprocess.run([sys.executable, FRAMEWORK_SCRIPT] + sys.argv[1:]).returncode)
