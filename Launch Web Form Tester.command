#!/bin/bash
# ==============================================================================
# AI-Based Web Form Testing Framework - Desktop Application Launcher
# Double-click this file from macOS Finder or Desktop to launch the app.
# ==============================================================================

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# If launched from Desktop shortcut, resolve to Main Project
if [ ! -f "$DIR/run_dashboard.py" ]; then
    DIR="/Users/diazjensen/Desktop/Main Project"
fi

cd "$DIR"

echo "================================================================================"
echo " Starting AI Web Form Testing Application..."
echo " Opening interactive interface in your browser..."
echo "================================================================================"

PYTHON_BIN="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python3"
fi

# Launch the interactive web testing application
"$PYTHON_BIN" run_dashboard.py
