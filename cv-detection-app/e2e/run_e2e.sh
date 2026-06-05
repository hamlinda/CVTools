#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Optionally run inside docker compose
USE_DOCKER=0
if [ "${1:-}" = "--docker" ]; then
  USE_DOCKER=1
fi

echo "E2E: ensuring .env exists"
if [ ! -f .env ]; then
  cp .env.example .env
fi

VENV_DIR=".e2e_venv"
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

echo "Installing minimal backend deps (httpx, python-dotenv, fastapi, uvicorn)"
pip install --upgrade pip
pip install "python-dotenv>=1.0.0" httpx fastapi uvicorn pillow python-multipart opencv-python-headless

if [ "$USE_DOCKER" -eq 1 ]; then
  echo "Starting services with Docker Compose..."
  ./start-with-docker.sh
  # We will manage cleanup with docker compose down
else
  echo "Starting backend (in background)"
  python3 -u -m backend.main &
  BACKEND_PID=$!
  echo "backend pid=$BACKEND_PID"
fi

cleanup() {
  echo "Cleaning up..."
  if [ "$USE_DOCKER" -eq 1 ]; then
    echo "Tearing down docker compose services..."
    docker compose down || true
  else
    if kill -0 "$BACKEND_PID" 2>/dev/null; then
      kill "$BACKEND_PID" || true
      wait "$BACKEND_PID" 2>/dev/null || true
    fi
  fi
}
trap cleanup EXIT

echo "Waiting for .port_binding to be written by backend..."
ATTEMPTS=0
PORT_BIND_FILE=".port_binding"
until [ -f "$PORT_BIND_FILE" ] || [ $ATTEMPTS -ge 30 ]; do
  ATTEMPTS=$((ATTEMPTS+1))
  sleep 1
done
if [ $ATTEMPTS -ge 30 ]; then
  echo "Timeout waiting for .port_binding" >&2
  exit 2
fi
PORT=$(cat "$PORT_BIND_FILE" | tr -d '\n' || true)
if [ -z "$PORT" ]; then
  echo "Failed to read port from $PORT_BIND_FILE" >&2
  exit 2
fi

echo "Backend reported port=$PORT"
echo "Waiting for /api/status to become available on port $PORT..."
ATTEMPTS=0
until curl -sS http://localhost:$PORT/api/status > /tmp/e2e_status.json 2>/dev/null || [ $ATTEMPTS -ge 30 ]; do
  ATTEMPTS=$((ATTEMPTS+1))
  sleep 1
done
if [ $ATTEMPTS -ge 30 ]; then
  echo "Timeout waiting for backend status on port $PORT" >&2
  cat /tmp/e2e_status.json || true
  exit 2
fi

echo "Backend status:"
cat /tmp/e2e_status.json

echo "Creating test image"
python3 e2e/create_test_image.py

echo "Posting test image to /api/analyze-image"
RESPONSE_FILE=/tmp/e2e_analyze.json

curl -sS -X POST -F "file=@e2e_test.jpg;type=image/jpeg" http://localhost:$PORT/api/analyze-image -o "$RESPONSE_FILE" || true
echo "Analyze response:"; cat "$RESPONSE_FILE"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST -F "file=@e2e_test.jpg;type=image/jpeg" http://localhost:$PORT/api/analyze-image || true)
if [ "$HTTP_CODE" = "200" ]; then
  echo "Image analysis endpoint returned 200"
else
  echo "Image analysis endpoint returned $HTTP_CODE (may indicate Ollama not reachable)"
fi

echo "Requesting graceful shutdown"
curl -s -X POST http://localhost:$PORT/api/stop || true

echo "E2E complete"
