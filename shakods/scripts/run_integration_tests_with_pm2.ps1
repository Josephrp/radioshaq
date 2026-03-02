# Start PM2 API in test env, run integration tests (including live_api), then stop PM2.
# Usage: from shakods:
#   PowerShell: .\scripts\run_integration_tests_with_pm2.ps1
#   Git Bash:   ./scripts/run_integration_tests_with_pm2.sh  (use / not \)
# Requires: Node.js, PM2 (npm i -g pm2), and optional Docker Postgres on 5434.

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $Root

$TestPort = if ($env:TEST_PORT) { $env:TEST_PORT } else { "8001" }
$BaseUrl = "http://127.0.0.1:$TestPort"
$env:BASE_URL = $BaseUrl

# Ensure PM2 is available
$pm2 = Get-Command pm2 -ErrorAction SilentlyContinue
if (-not $pm2) {
  Write-Error "PM2 not found. Install with: npm i -g pm2"
  exit 1
}

# Stop any existing shakods-api
pm2 delete shakods-api 2>$null
Start-Sleep -Seconds 1

Write-Host "Starting shakods-api with PM2 (env test, port $TestPort)..."
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

Write-Host "Running unit + integration tests (including live_api)..."
uv run pytest tests/unit tests/integration -v --tb=short -m "unit or integration or live_api"
if (-not $?) { $exitCode = $LASTEXITCODE }
pm2 stop shakods-api
Write-Host "PM2 shakods-api stopped."
if ($null -eq $exitCode) { $exitCode = 0 }
exit $exitCode
