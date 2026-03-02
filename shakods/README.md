# 📡 SHAKODS

**S**trategic **A**utonomous **H**am **R**adio and **K**nowledge **O**perations **D**ispatch **S**ystem

A specialized AI-powered orchestrator for ham radio operations, emergency communications, and field-to-HQ coordination.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Install (get everything correctly)

**Prerequisites:** Python 3.11+, [uv](https://github.com/astral-sh/uv). Optional: Docker (Postgres), Node.js (PM2).

From the **shakods** directory:

```powershell
# One command: install deps + dev + test
uv sync --extra dev --extra test
```

**Full automated setup (Windows):** installs deps, creates config, starts Docker Postgres on port 5434, runs migrations, installs PM2 if Node is present:

```powershell
.\infrastructure\local\setup.ps1
```

See **[docs/install.md](docs/install.md)** for the full install guide (prerequisites, DB, PM2, troubleshooting).

## Quick Start

```bash
# 1. Start PostgreSQL (Docker, port 5434)
cd infrastructure/local && docker compose up -d postgres && cd ../..

# 2. Run migrations
uv run alembic -c infrastructure/local/alembic.ini upgrade head

# 3. Start API
uv run python -m shakods.api.server
# API: http://localhost:8000/docs
```

See [docs/database.md](docs/database.md) for database URL and Alembic usage.

## Authentication

Most endpoints require a **Bearer JWT**. Get a token (no auth required) then send it on each request.

```powershell
# Get token (PowerShell)
$r = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/auth/token?subject=op1&role=field&station_id=STATION-01"
$env:TOKEN = $r.access_token

# Use it
Invoke-RestMethod -Uri "http://localhost:8000/auth/me" -Headers @{ Authorization = "Bearer $env:TOKEN" }
```

```bash
# Get token (Bash)
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=STATION-01" | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/auth/me
```

Roles: `field` (default), `hq`, `receiver`. Full details: [docs/auth.md](docs/auth.md).

## Demo (inject, relay, poll)

With the API running, in a second terminal:

```powershell
uv run python scripts/demo/run_demo.py
```

The script gets its own token from `POST /auth/token` (subject `demo-op1`, role `field`) and then injects on 40m, relays to 2m, and polls `/transcripts`. No manual auth needed. See [scripts/demo/README.md](scripts/demo/README.md) and [docs/demo-two-local-one-remote.md](docs/demo-two-local-one-remote.md).

## Development

```bash
# Run tests
uv run pytest tests/unit tests/integration -v

# Type check
uv run mypy shakods

# Lint / format
uv run ruff check . && uv run ruff format .
```

## License

MIT
