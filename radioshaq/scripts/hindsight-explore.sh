#!/usr/bin/env bash
# Optional: run Hindsight TUI explorer (or UI) with API URL from env or default.
# Requires Hindsight CLI: https://hindsight.vectorize.io/sdks/cli
# Banks for RadioShaq are named radioshaq-{CALLSIGN} (e.g. radioshaq-W1ABC).

export HINDSIGHT_API_URL="${HINDSIGHT_API_URL:-${RADIOSHAQ_MEMORY__HINDSIGHT_BASE_URL:-http://localhost:8888}}"
echo "Using HINDSIGHT_API_URL=$HINDSIGHT_API_URL"
if [ "$1" = "ui" ]; then
  hindsight ui
else
  hindsight explore
fi
