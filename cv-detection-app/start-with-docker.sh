#!/usr/bin/env bash
set -euo pipefail

# Build and start services (backend + frontend) with docker-compose
cd "$(dirname "$0")"
echo "Building and starting backend + frontend via docker-compose..."

# Start backend+frontend together; Ollama is expected to be reachable via network (OLLAMA_HOST)
docker compose up --build -d backend frontend

echo "Waiting for backend to report status..."
# Poll /api/status on localhost mapped port
PORT=${APP_PORT_PREFERRED:-8080}
for i in {1..30}; do
  if curl -sSf http://localhost:${PORT}/api/status >/dev/null 2>&1; then
    echo "Backend is up at http://localhost:${PORT}"
    exit 0
  fi
  sleep 1
done

echo "Timed out waiting for backend. Use 'docker compose ps' to inspect services." >&2
exit 2
