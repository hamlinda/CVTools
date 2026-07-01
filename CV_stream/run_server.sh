#!/usr/bin/env sh
# CV Stream — Linux inference server launcher
# Run this on the Linux host (via SSH terminal or as a background service).
# Usage:  sh run_server.sh [--port 5000]
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

find_python() {
    for cmd in python3.13 python3.12 python3.11 python3.10 python3.9 python3.8 python3 python; do
        if command -v "$cmd" >/dev/null 2>&1; then
            ver=$("$cmd" -c "import sys; print(sys.version_info >= (3,8))" 2>/dev/null || echo "False")
            if [ "$ver" = "True" ]; then
                echo "$cmd"; return
            fi
        fi
    done
    echo ""
}

PY=$(find_python)

if [ -z "$PY" ]; then
    echo ""
    echo "ERROR: Python 3.8+ not found."
    echo "  Ubuntu/Debian : sudo apt install python3"
    echo "  Fedora/RHEL   : sudo dnf install python3"
    exit 1
fi

echo "Python : $PY ($("$PY" --version))"
echo ""
echo "Server will be reachable at one of these addresses:"
hostname -I 2>/dev/null | tr ' ' '\n' | grep -v '^$' | while read -r ip; do
    echo "  http://${ip}:5000"
done
echo ""

nohup "$PY" "$SCRIPT_DIR/tracker_server.py" "$@" > "$SCRIPT_DIR/server.log" 2>&1 &
echo "Server started in background (PID: $!)."
echo "Log file: $SCRIPT_DIR/server.log"

