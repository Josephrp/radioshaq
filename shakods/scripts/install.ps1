# Minimal install: sync Python deps with uv (from shakods directory).
# For full setup (Docker, PM2, config), run: .\infrastructure\local\setup.ps1

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $Root

if (-not (Test-Path "pyproject.toml")) {
    Write-Error "Run from shakods directory (pyproject.toml not found)."
    exit 1
}

$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host "uv is required. Install: pip install uv" -ForegroundColor Yellow
    Write-Host "See https://github.com/astral-sh/uv#installation"
    exit 1
}

Write-Host "Installing dependencies (uv sync --extra dev --extra test)..." -ForegroundColor Cyan
uv sync --extra dev --extra test
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Done. Verify: uv run pytest tests/unit -v --tb=short" -ForegroundColor Green
Write-Host "Full setup (Docker, PM2): .\infrastructure\local\setup.ps1" -ForegroundColor Cyan
Write-Host "Install guide: docs/install.md" -ForegroundColor Cyan
