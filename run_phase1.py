#!/usr/bin/env python3
"""
Phase 1 Master Launcher: AI-based Web Form Testing Framework
Self-delegates to the framework environment containing all dependencies.
"""
import os
import sys

TARGET_PYTHON = "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
HERE = os.path.dirname(os.path.abspath(__file__))
FRAMEWORK_SCRIPT = os.path.join(HERE, "ai-form-test-framework", "run_phase1.py")

# Transparently switch to Python 3.11 environment if needed
if os.path.exists(TARGET_PYTHON) and sys.executable != TARGET_PYTHON:
    os.execv(TARGET_PYTHON, [TARGET_PYTHON, FRAMEWORK_SCRIPT] + sys.argv[1:])
else:
    # Run directly
    import subprocess
    sys.exit(subprocess.run([sys.executable, FRAMEWORK_SCRIPT] + sys.argv[1:]).returncode)
