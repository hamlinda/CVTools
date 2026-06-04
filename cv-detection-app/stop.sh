#!/usr/bin/env bash
set -euo pipefail

# Attempts to shutdown the running backend via API
if curl -s -X POST http://localhost:${APP_PORT_PREFERRED:-8080}/api/stop; then
  echo "Stop requested"
else
  echo "Failed to request stop or backend not running"
fi
