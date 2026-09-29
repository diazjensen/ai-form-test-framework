#!/usr/bin/env python3
"""
Dashboard Launcher: Quality Intelligence Dashboard (Streamlit).
Delegates to the Python 3.11 environment containing Streamlit and all dependencies.
"""
import os
import sys

TARGET_PYTHON = "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
HERE = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_SCRIPT = os.path.join(HERE, "ai-form-test-framework", "dashboard", "streamlit_app.py")

if os.path.exists(TARGET_PYTHON) and sys.executable != TARGET_PYTHON:
    os.execv(TARGET_PYTHON, [TARGET_PYTHON, "-m", "streamlit", "run", DASHBOARD_SCRIPT] + sys.argv[1:])
else:
    import subprocess
    sys.exit(subprocess.run([sys.executable, "-m", "streamlit", "run", DASHBOARD_SCRIPT] + sys.argv[1:]).returncode)
