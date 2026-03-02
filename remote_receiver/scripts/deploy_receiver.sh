#!/usr/bin/env bash
# Deploy SHAKODS remote receiver on Raspberry Pi (or similar Linux).
# Usage: ./scripts/deploy_receiver.sh

set -e
echo "SHAKODS Remote Receiver - Raspberry Pi deploy"

# Optional: create venv and install
if [ -z "$VIRTUAL_ENV" ]; then
  if command -v uv >/dev/null 2>&1; then
    uv sync
    source .venv/bin/activate
  else
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .
  fi
fi

# Required env (set in systemd or .env)
: "${JWT_SECRET:?Set JWT_SECRET}"
: "${STATION_ID:=RECEIVER}"
export HQ_URL="${HQ_URL:-http://hq:8000}"
export HQ_TOKEN="${HQ_TOKEN:-}"

echo "Starting receiver (STATION_ID=$STATION_ID)..."
exec uvicorn receiver.server:app --host 0.0.0.0 --port 8765
