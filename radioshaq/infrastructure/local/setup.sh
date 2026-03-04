#!/usr/bin/env bash
# RadioShaq Local Development Setup Script (Bash – Linux/macOS)
# Usage: from radioshaq directory: ./infrastructure/local/setup.sh
#        or: bash infrastructure/local/setup.sh

set -e

# Project root = two levels up from infrastructure/local
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
  echo "Error: Must run from radioshaq directory; expected pyproject.toml in $PROJECT_ROOT" >&2
  exit 1
fi

cd "$PROJECT_ROOT"

echo "Setting up RadioShaq local development environment"

# 1. Check prerequisites
echo "Checking prerequisites..."

UV_AVAILABLE=false
if command -v uv >/dev/null 2>&1; then
  UV_AVAILABLE=true
  echo "uv found: $(uv --version)"
fi

if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
  echo "Python 3.11+ is required" >&2
  exit 1
fi
PYTHON_CMD="$(command -v python3 2>/dev/null || command -v python)"
echo "Python found: $($PYTHON_CMD --version)"

NODE_AVAILABLE=false
if command -v node >/dev/null 2>&1; then
  NODE_AVAILABLE=true
  echo "Node.js found: $(node --version)"
else
  echo "Node.js not found - PM2 and bridge will not be available"
fi

DOCKER_AVAILABLE=false
if command -v docker >/dev/null 2>&1; then
  DOCKER_AVAILABLE=true
  echo "Docker found: $(docker --version)"
else
  echo "Docker not found - database must be configured manually"
fi

# 2. Install Python dependencies (uv or pip)
echo ""
echo "Installing Python dependencies..."
if [ "$UV_AVAILABLE" = true ]; then
  uv sync --extra dev --extra test
  echo "RadioShaq and dev/test deps installed (uv)"
else
  if [ ! -d ".venv" ]; then
    "$PYTHON_CMD" -m venv .venv
    echo "Virtual environment created"
  fi
  # shellcheck source=/dev/null
  . .venv/bin/activate
  pip install -e ".[dev,test]"
  echo "RadioShaq and dev/test deps installed (pip)"
fi

# 3. Create necessary directories
echo ""
echo "Creating directories..."
for dir in logs .radioshaq .radioshaq/data .radioshaq/config; do
  mkdir -p "$dir"
done
echo "Directories created"

# 4. Create default config (port 5434 = Docker Postgres mapping)
echo ""
echo "Creating default configuration..."
CONFIG_PATH=".radioshaq/config.yaml"
if [ ! -f "$CONFIG_PATH" ]; then
  cat > "$CONFIG_PATH" << 'CONFIGEOF'
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
  port: /dev/ttyUSB0

field:
  station_id: DEV-FIELD-01
  sync_interval_seconds: 60

pm2:
  watch: true
CONFIGEOF
  echo "Default config created at $CONFIG_PATH"
else
  echo "Config already exists"
fi

# 5. Setup Docker services (if Docker is available) – Postgres on port 5434, optional Hindsight
if [ "$DOCKER_AVAILABLE" = true ]; then
  echo ""
  echo "Setting up Docker services..."
  COMPOSE_CMD="docker compose"
  if ! docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
  fi

  START_HINDSIGHT=false
  if [ -z "${CI:-}" ]; then
    read -r -p "Start Hindsight (semantic memory) in Docker too? [y/N] " resp
    case "$resp" in
      [yY]*) START_HINDSIGHT=true ;;
    esac
  fi

  echo "Starting PostgreSQL (port 5434)..."
  cd "$PROJECT_ROOT/infrastructure/local"
  if [ "$START_HINDSIGHT" = true ]; then
    $COMPOSE_CMD --profile hindsight up -d postgres hindsight
  else
    $COMPOSE_CMD up -d postgres
  fi
  cd "$PROJECT_ROOT"

  echo "Waiting for PostgreSQL at 127.0.0.1:5434..."
  PG_URL="postgresql+asyncpg://radioshaq:radioshaq@127.0.0.1:5434/radioshaq"
  MAX_ATTEMPTS=30
  attempt=0
  ready=false

  while [ $attempt -lt $MAX_ATTEMPTS ]; do
    sleep 1
    attempt=$((attempt + 1))
    if [ "$UV_AVAILABLE" = true ]; then
      result=$(uv run python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test():
    try:
        engine = create_async_engine('$PG_URL')
        async with engine.connect() as conn:
            await conn.execute(text('SELECT 1'))
        return True
    except Exception:
        return False
print(asyncio.run(test()))
" 2>/dev/null || echo "False")
    else
      result=$("$PROJECT_ROOT/.venv/bin/python" -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def test():
    try:
        engine = create_async_engine('$PG_URL')
        async with engine.connect() as conn:
            await conn.execute(text('SELECT 1'))
        return True
    except Exception:
        return False
print(asyncio.run(test()))
" 2>/dev/null || echo "False")
    fi
    if [ "$result" = "True" ]; then
      ready=true
      break
    fi
    if [ $((attempt % 5)) -eq 0 ]; then
      echo "  Attempt $attempt/$MAX_ATTEMPTS..."
    fi
  done

  if [ "$ready" = true ]; then
    echo "PostgreSQL is ready"
    echo "Running database migrations..."
    if [ "$UV_AVAILABLE" = true ]; then
      uv run alembic -c infrastructure/local/alembic.ini upgrade head
    else
      "$PROJECT_ROOT/.venv/bin/alembic" -c infrastructure/local/alembic.ini upgrade head
    fi
    echo "Database migrations complete"
  else
    echo "PostgreSQL did not become ready in time"
  fi
fi

# 6. Install PM2 globally (if Node.js is available)
if [ "$NODE_AVAILABLE" = true ]; then
  echo ""
  echo "Installing PM2..."
  if npm install -g pm2 2>/dev/null; then
    echo "PM2 installed (pm2 --version to verify)"
  else
    echo "PM2 install failed; you may need to use sudo or fix npm global bin PATH"
  fi
fi

# 7. Summary
echo ""
echo "========================================"
echo "RadioShaq setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Set API keys: export MISTRAL_API_KEY='your_key'"
echo "  2. Start dependencies + API (CLI):"
echo "       radioshaq launch docker              # Postgres only"
echo "       radioshaq launch docker --hindsight  # Postgres + Hindsight"
echo "       radioshaq launch pm2                 # Docker Postgres + PM2 API"
echo "       radioshaq launch pm2 --hindsight     # + Hindsight via PM2"
echo "     Or manually: uv run python -m radioshaq.api.server"
echo "     Or PM2:      pm2 start infrastructure/local/ecosystem.config.js --only radioshaq-api"
echo "  3. Run tests:   uv run pytest tests/unit tests/integration -v"
echo "  4. API docs:    http://localhost:8000/docs"
echo ""
echo "See docs/install.md for full install guide."
