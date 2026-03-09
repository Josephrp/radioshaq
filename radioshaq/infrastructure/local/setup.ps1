# RadioShaq Local Development Setup Script (PowerShell)
# Usage: from radioshaq directory: .\infrastructure\local\setup.ps1

$ErrorActionPreference = "Stop"

Write-Host "Setting up RadioShaq local development environment" -ForegroundColor Cyan

# Project root = two levels up from infrastructure/local
$ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
if (-not (Test-Path (Join-Path $ProjectRoot "pyproject.toml"))) {
    Write-Host "Error: Must run from radioshaq directory; expected pyproject.toml in $ProjectRoot" -ForegroundColor Red
    exit 1
}
Set-Location $ProjectRoot

# 1. Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Yellow

# Prefer uv
$uvAvailable = $false
$uvVersion = uv --version 2>&1
if ($LASTEXITCODE -eq 0) {
    $uvAvailable = $true
    Write-Host "uv found: $uvVersion"
}

# Check Python (required)
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python 3.11+ is required" -ForegroundColor Red
    exit 1
}
Write-Host "Python found: $pythonVersion"

# Check Node.js (optional, for PM2)
$nodeVersion = node --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Node.js not found - PM2 and bridge will not be available" -ForegroundColor Yellow
} else {
    Write-Host "Node.js found: $nodeVersion"
}

# Check Docker (optional)
$dockerVersion = docker --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker not found - database must be configured manually" -ForegroundColor Yellow
} else {
    Write-Host "Docker found: $dockerVersion"
}

# 2. Install Python dependencies (uv or pip)
Write-Host "`nInstalling Python dependencies..." -ForegroundColor Yellow
if ($uvAvailable) {
    uv sync --extra dev --extra test
    Write-Host "RadioShaq and dev/test deps installed (uv)"
    Write-Host "Optional: uv sync --extra audio (ASR: Voxtral, Whisper; Scribe uses API). Optional: uv sync --extra tts_kokoro (local TTS: Kokoro)."
} else {
    if (-not (Test-Path ".venv")) {
        python -m venv .venv
        Write-Host "Virtual environment created"
    }
    & .venv\Scripts\Activate.ps1
    pip install -e ".[dev,test]"
    Write-Host "RadioShaq and dev/test deps installed (pip)"
}

# 3. Create necessary directories
Write-Host "`nCreating directories..." -ForegroundColor Yellow
$dirs = @("logs", ".radioshaq", ".radioshaq\data", ".radioshaq\config")
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "Directories created"

# 4. Create default config (port 5434 = Docker Postgres mapping)
Write-Host "`nCreating default configuration..." -ForegroundColor Yellow
$configPath = ".radioshaq\config.yaml"
if (-not (Test-Path $configPath)) {
    @"
# RadioShaq Local Development Configuration
mode: field
station_id: DEV-STATION
debug: true
log_level: DEBUG

database:
  postgres_url: postgresql+asyncpg://radioshaq:radioshaq@127.0.0.1:5434/radioshaq
  auto_migrate: true

jwt:
  secret_key: dev-secret-change-in-production
  access_token_expire_minutes: 60

llm:
  provider: mistral
  model: mistral-large-latest
  # Set MISTRAL_API_KEY environment variable

radio:
  enabled: false
  port: COM3

tts:
  provider: elevenlabs
  # For kokoro (local TTS): set provider to kokoro and run uv sync --extra tts_kokoro
  # For elevenlabs: set ELEVENLABS_API_KEY

field:
  station_id: DEV-FIELD-01
  sync_interval_seconds: 60

pm2:
  watch: true
"@ | Out-File -FilePath $configPath -Encoding UTF8
    Write-Host "Default config created at $configPath"
} else {
    Write-Host "Config already exists"
}

# 5. Setup Docker services (if Docker is available) – Postgres on port 5434, optional Hindsight
if ($dockerVersion) {
    Write-Host "`nSetting up Docker services..." -ForegroundColor Yellow
    $composeCmd = "docker compose"
    $null = & docker compose version 2>&1
    if ($LASTEXITCODE -ne 0) {
        $composeCmd = "docker-compose"
    }
    $startHindsight = $false
    if (-not $env:CI) {
        $resp = Read-Host "Start Hindsight (semantic memory) in Docker too? [y/N]"
        if ($resp -match '^[yY]') { $startHindsight = $true }
    }
    Write-Host "Starting PostgreSQL (port 5434)..."
    Push-Location infrastructure\local
    if ($startHindsight) {
        & $composeCmd --profile hindsight up -d postgres hindsight
    } else {
        & $composeCmd up -d postgres
    }
    Pop-Location

    Write-Host "Waiting for PostgreSQL at 127.0.0.1:5434..."
    $maxAttempts = 30
    $attempt = 0
    $ready = $false
    $pgUrl = "postgresql+asyncpg://radioshaq:radioshaq@127.0.0.1:5434/radioshaq"
    while ($attempt -lt $maxAttempts -and -not $ready) {
        Start-Sleep -Seconds 1
        $attempt++
        try {
            if ($uvAvailable) {
                $result = uv run python -c @"
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test():
    try:
        engine = create_async_engine('$pgUrl')
        async with engine.connect() as conn:
            await conn.execute(text('SELECT 1'))
        return True
    except Exception:
        return False
print(asyncio.run(test()))
"@ 2>&1
            } else {
                $result = & .venv\Scripts\python.exe -c @"
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test():
    try:
        engine = create_async_engine('$pgUrl')
        async with engine.connect() as conn:
            await conn.execute(text('SELECT 1'))
        return True
    except Exception:
        return False
print(asyncio.run(test()))
"@ 2>&1
            }
            if ($result -match "True") { $ready = $true }
        } catch { }
        if ($attempt % 5 -eq 0) { Write-Host "  Attempt $attempt/$maxAttempts..." }
    }
    if ($ready) {
        Write-Host "PostgreSQL is ready"
        Write-Host "Running database migrations..."
        if ($uvAvailable) {
            uv run alembic -c infrastructure/local/alembic.ini upgrade head
        } else {
            & .venv\Scripts\alembic.exe -c infrastructure\local\alembic.ini upgrade head
        }
        Write-Host "Database migrations complete"
    } else {
        Write-Host "PostgreSQL did not become ready in time" -ForegroundColor Yellow
    }
}

# 6. Install PM2 globally (if Node.js is available)
if ($nodeVersion) {
    Write-Host "`nInstalling PM2..." -ForegroundColor Yellow
    npm install -g pm2 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "PM2 installed (pm2 --version to verify)"
    } else {
        Write-Host "PM2 install failed; you may need to add npm global bin to PATH (e.g. %APPDATA%\npm)" -ForegroundColor Yellow
    }
}

# 7. Summary
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "RadioShaq setup complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Set API keys: `$env:MISTRAL_API_KEY = 'your_key'"
Write-Host "  2. Start dependencies + API (CLI):"
Write-Host "       radioshaq launch docker              # Postgres only"
Write-Host "       radioshaq launch docker --hindsight # Postgres + Hindsight"
Write-Host "       radioshaq launch pm2                # Docker Postgres + PM2 API"
Write-Host "       radioshaq launch pm2 --hindsight    # + Hindsight via PM2"
Write-Host "     Or manually: uv run python -m radioshaq.api.server"
Write-Host "     Or PM2:      pm2 start infrastructure/local/ecosystem.config.js --only radioshaq-api"
Write-Host "  3. Run tests:   uv run pytest tests/unit tests/integration -v"
Write-Host "  4. API docs:    http://localhost:8000/docs"
Write-Host ""
Write-Host "See docs/install.md for full install guide." -ForegroundColor Cyan
