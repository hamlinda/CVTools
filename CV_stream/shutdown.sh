#!/usr/bin/env sh
# CV Stream — Service Shutdown Script
# Closes running inference server and tracking client processes.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Scanning for running CV Stream processes..."

# Identify PIDs
# We look for tracker_server.py, tracker.py, and tracker_client.py
# Using pgrep -f ensures we find them even if running inside a virtual environment.
PIDS=""

for pattern in "tracker_server.py" "tracker.py" "tracker_client.py"; do
    # Find PIDs excluding the shutdown script itself
    found_pids=$(pgrep -f "$pattern" | grep -v "$$" 2>/dev/null)
    if [ -n "$found_pids" ]; then
        for pid in $found_pids; do
            # Verify the pid is a valid number and process exists
            if kill -0 "$pid" 2>/dev/null; then
                # Get the process command line for display
                cmdline=$(ps -p "$pid" -o args= 2>/dev/null)
                echo "Found process $pid: $cmdline"
                PIDS="$PIDS $pid"
            fi
        done
    fi
done

# Also check for processes on port 5000
if command -v lsof >/dev/null 2>&1; then
    port_pids=$(lsof -t -i :5000 2>/dev/null)
    if [ -n "$port_pids" ]; then
        for pid in $port_pids; do
            if kill -0 "$pid" 2>/dev/null; then
                # Avoid duplicate entries
                case " $PIDS " in
                    *" $pid "*) ;;
                    *)
                        cmdline=$(ps -p "$pid" -o args= 2>/dev/null)
                        echo "Found process $pid listening on port 5000: $cmdline"
                        PIDS="$PIDS $pid"
                        ;;
                esac
            fi
        done
    fi
fi

# Clean up whitespace
PIDS=$(echo "$PIDS" | xargs)

if [ -z "$PIDS" ]; then
    echo "No running CV Stream services found."
    exit 0
fi

echo "Stopping services (PIDs: $PIDS)..."
# Try graceful termination first (SIGTERM)
kill $PIDS 2>/dev/null

# Wait up to 3 seconds for processes to terminate
for i in 1 2 3; do
    still_running=""
    for pid in $PIDS; do
        if kill -0 "$pid" 2>/dev/null; then
            still_running="$still_running $pid"
        fi
    done
    still_running=$(echo "$still_running" | xargs)
    if [ -z "$still_running" ]; then
        break
    fi
    sleep 1
done

# Force terminate if still running
still_running=""
for pid in $PIDS; do
    if kill -0 "$pid" 2>/dev/null; then
        still_running="$still_running $pid"
    fi
done
still_running=$(echo "$still_running" | xargs)

if [ -n "$still_running" ]; then
    echo "Force killing remaining processes: $still_running"
    kill -9 $still_running 2>/dev/null
fi

echo "Shutdown complete."
