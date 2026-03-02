#!/usr/bin/env bash
# Start PM2 API in test env, run integration tests (including live_api), then stop PM2.
# Usage: from shakods or monorepo root:
#   ./scripts/run_integration_tests_with_pm2.sh   (Git Bash/WSL)
#   .\scripts\run_integration_tests_with_pm2.ps1   (PowerShell, from shakods)
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"
powershell -NoProfile -ExecutionPolicy Bypass -File "$SCRIPT_DIR/run_integration_tests_with_pm2.ps1"
