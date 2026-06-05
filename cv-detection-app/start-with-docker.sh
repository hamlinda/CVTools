#!/usr/bin/env bash
set -euo pipefail

# Build and start services (Ollama + backend) with docker-compose
cd "$(dirname "$0")"

echo "Building and starting Ollama + backend via docker-compose (backend+ollama only)..."
# Start only the ollama and backend services to avoid frontend port conflicts during CI/dev runs
HOST_OLLAMA_IN_USE=0
HOST_BACKEND_IN_USE=0
if ss -lnt | grep -q ':11434'; then
  HOST_OLLAMA_IN_USE=1
fi
if ss -lnt | grep -q ":${APP_PORT_PREFERRED:-8080}"; then
  HOST_BACKEND_IN_USE=1
fi

if [ "$HOST_OLLAMA_IN_USE" -eq 1 ] && [ "$HOST_BACKEND_IN_USE" -eq 1 ]; then
  echo "Both Ollama (11434) and backend (${APP_PORT_PREFERRED:-8080}) ports are already in use on the host — nothing to start."
  exit 0
fi

if [ "$HOST_OLLAMA_IN_USE" -eq 1 ]; then
  echo "Port 11434 already in use — starting backend only."
  docker compose up --build -d backend
  exit 0
fi

if [ "$HOST_BACKEND_IN_USE" -eq 1 ]; then
  echo "Port ${APP_PORT_PREFERRED:-8080} already in use — starting Ollama only."
  docker compose up --build -d ollama
  exit 0
fi

# Otherwise start both
docker compose up --build -d ollama backend

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
