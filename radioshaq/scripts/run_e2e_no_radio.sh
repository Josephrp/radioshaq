#!/usr/bin/env bash
# E2E tests without radio: start API (test env), run integration + live_api, stop API.
# Usage: from radioshaq: ./scripts/run_e2e_no_radio.sh
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

TEST_PORT="${TEST_PORT:-8001}"
BASE_URL="http://127.0.0.1:${TEST_PORT}"
export BASE_URL
export RADIOSHAQ_RADIO__ENABLED=false
export RADIOSHAQ_RADIO__AUDIO_INPUT_ENABLED=false
export RADIO_ENABLED=false

command -v pm2 >/dev/null 2>&1 || { echo "PM2 not found. Install: npm i -g pm2"; exit 1; }

pm2 delete radioshaq-api 2>/dev/null || true
sleep 1

echo "Starting radioshaq-api (test env, no radio), port ${TEST_PORT}..."
pm2 start ecosystem.config.js --only radioshaq-api --env test
pm2 save --force 2>/dev/null || true

echo "Waiting for API at ${BASE_URL}/health (up to 30s)..."
ok=0
i=0
while [ $i -lt 30 ]; do
  i=$((i + 1))
  if curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/health" 2>/dev/null | grep -q 200; then
    ok=1
    echo "API is up."
    break
  fi
  sleep 1
done
if [ "$ok" = 0 ]; then
  echo "API did not become ready in time."
  pm2 logs radioshaq-api --lines 20 --nostream
  pm2 stop radioshaq-api
  exit 1
fi

echo "Running E2E tests (integration + live_api, no radio)..."
uv run pytest tests/integration -v --tb=short -m "integration and live_api"
exit_code=$?
pm2 stop radioshaq-api
echo "PM2 radioshaq-api stopped."
exit $exit_code
