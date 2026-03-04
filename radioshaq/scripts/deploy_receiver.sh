#!/usr/bin/env bash
# Deploy remote receiver on Raspberry Pi (or similar Linux).
# Usage: from radioshaq/: ./scripts/deploy_receiver.sh
# Requires: pip install radioshaq (or uv sync) and optionally radioshaq[sdr] or radioshaq[hackrf]

set -e
echo "RadioShaq Remote Receiver - Raspberry Pi deploy"

# Optional: create venv and install from radioshaq/
if [ -z "$VIRTUAL_ENV" ]; then
  if command -v uv >/dev/null 2>&1; then
    uv sync --extra sdr --extra hackrf
    source .venv/bin/activate
  else
    python3 -m venv .venv
    source .venv/bin/activate
    pip install '.[sdr,hackrf]'
  fi
fi

# Required env (set in systemd or .env)
: "${JWT_SECRET:?Set JWT_SECRET}"
: "${STATION_ID:=RECEIVER}"
export HQ_URL="${HQ_URL:-http://hq:8000}"
export HQ_TOKEN="${HQ_TOKEN:-}"

echo "Starting receiver (STATION_ID=$STATION_ID)..."
exec radioshaq run-receiver --host 0.0.0.0 --port 8765
