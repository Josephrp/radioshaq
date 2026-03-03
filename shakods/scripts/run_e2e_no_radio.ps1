# E2E tests without radio: start API (test env, radio disabled), run integration + live_api, stop API.
# Usage: from shakods directory:
#   .\scripts\run_e2e_no_radio.ps1
# Or run the PM2 e2e app after starting the API manually:
#   pm2 start shakods-api --env test
#   pm2 start ecosystem.config.js --only shakods-e2e
# Requires: Node.js, PM2, uv (or pytest in venv).

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $Root

$TestPort = if ($env:TEST_PORT) { $env:TEST_PORT } else { "8001" }
$BaseUrl = "http://127.0.0.1:$TestPort"
$env:BASE_URL = $BaseUrl
$env:SHAKODS_RADIO__ENABLED = "false"
$env:SHAKODS_RADIO__AUDIO_INPUT_ENABLED = "false"
$env:RADIO_ENABLED = "false"

$pm2 = Get-Command pm2 -ErrorAction SilentlyContinue
if (-not $pm2) {
  Write-Error "PM2 not found. Install with: npm i -g pm2"
  exit 1
}

try { pm2 delete shakods-api 2>&1 | Out-Null } catch { }
Start-Sleep -Seconds 1

Write-Host "Starting shakods-api (test env, no radio), port $TestPort..."
pm2 start ecosystem.config.js --only shakods-api --env test
pm2 save --force 2>$null

Write-Host "Waiting for API at $BaseUrl/health (up to 30s)..."
$ok = $false
for ($i = 1; $i -le 30; $i++) {
  try {
    $r = Invoke-WebRequest -Uri "$BaseUrl/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
    if ($r.StatusCode -eq 200) {
      $ok = $true
      Write-Host "API is up."
      break
    }
  } catch {}
  Start-Sleep -Seconds 1
}
if (-not $ok) {
  Write-Host "API did not become ready in time."
  pm2 logs shakods-api --lines 20 --nostream
  pm2 stop shakods-api
  exit 1
}

Write-Host "Running E2E tests (integration + live_api, no radio)..."
uv run pytest tests/integration -v --tb=short -m "integration and live_api"
$exitCode = $LASTEXITCODE
pm2 stop shakods-api
Write-Host "PM2 shakods-api stopped."
exit $exitCode
