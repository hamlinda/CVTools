#!/usr/bin/env sh
# CV Stream Tracker — macOS / Linux launcher
# Usage:  sh run.sh
#         ./run.sh          (after: chmod +x run.sh)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Find a suitable Python 3.8+
find_python() {
    for cmd in python3.13 python3.12 python3.11 python3.10 python3.9 python3.8 python3 python; do
        if command -v "$cmd" >/dev/null 2>&1; then
            ver=$("$cmd" -c "import sys; print(sys.version_info >= (3,8))" 2>/dev/null || echo "False")
            if [ "$ver" = "True" ]; then
                echo "$cmd"
                return
            fi
        fi
    done
    echo ""
}

PY=$(find_python)

if [ -z "$PY" ]; then
    echo ""
    echo "ERROR: Python 3.8+ not found."
    echo ""
    echo "  macOS  : brew install python   OR  download from https://python.org"
    echo "  Ubuntu : sudo apt install python3"
    echo "  Fedora : sudo dnf install python3"
    echo ""
    exit 1
fi

echo "Using: $PY ($("$PY" --version))"
exec "$PY" "$SCRIPT_DIR/tracker.py" "$@"
