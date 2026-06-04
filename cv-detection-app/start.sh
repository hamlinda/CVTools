#!/usr/bin/env bash
set -euo pipefail

# Load env if present
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

APP_HOST=${APP_HOST:-0.0.0.0}
APP_PORT_PREFERRED=${APP_PORT_PREFERRED:-8080}

PIDS=()

function cleanup() {
  echo "Stopping processes..."
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" || true
    fi
  done
  exit 0
}

trap cleanup SIGINT SIGTERM

echo "Starting backend..."
python3 -m backend.main &
PIDS+=("$!")

if [ "${1:-}" != "--no-frontend" ]; then
  echo "Starting frontend dev server..."
  (cd frontend && npm run dev) &
  PIDS+=("$!")
fi

wait
