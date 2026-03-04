# 📡 RadioShaq

**S**trategic **H**am **R**adio **A**utonomous **Q**uery and **K**ontrol System

A specialized AI-powered orchestrator for ham radio operations, emergency communications, and field-to-HQ coordination.

**Documentation:** [Quick Start](https://memyself.github.io/monorepo/quick-start/), [Configuration](https://memyself.github.io/monorepo/configuration/), [API Reference](https://memyself.github.io/monorepo/api-reference/) (published site). In-repo source: [../docs/](../docs/) (MkDocs Material).

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Install (get everything correctly)

**Prerequisites:** Python 3.11+, [uv](https://github.com/astral-sh/uv). Optional: Docker (Postgres), Node.js (PM2).

From the **radioshaq** directory:

```powershell
# One command: install deps + dev + test
uv sync --extra dev --extra test
```

**Full automated setup (Windows):** installs deps, creates config, starts Docker Postgres on port 5434, runs migrations, installs PM2 if Node is present:

```powershell
.\infrastructure\local\setup.ps1
```

See the [documentation site](https://memyself.github.io/monorepo/) (Quick Start, Configuration) or **[docs/install.md](docs/install.md)** for the full install guide (prerequisites, DB, PM2, troubleshooting).

## Quick Start

```bash
# 1. Start PostgreSQL (Docker, port 5434)
cd infrastructure/local && docker compose up -d postgres && cd ../..

# 2. Run migrations (use the runner script to avoid path issues on Windows)
python infrastructure/local/run_alembic.py upgrade head

# 3. Start API
uv run python -m radioshaq.api.server
# API: http://localhost:8000/docs
```

See [Configuration](https://memyself.github.io/monorepo/configuration/) or [docs/database.md](docs/database.md) for DATABASE_URL and migration commands (including the `run_alembic.py` script).

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

Roles: `field` (default), `hq`, `receiver`. Full details: [docs/auth.md](docs/auth.md). **Connecting real radios (IC-7300, FT-450D, FT-817, RTL-SDR):** see [Radio Usage](https://memyself.github.io/monorepo/radio-usage/) or [../docs/HARDWARE_CONNECTION.md](../docs/HARDWARE_CONNECTION.md) for CAT/Hamlib config and remote receiver deployment.

## Demo (inject, relay, poll)

With the API running, in a second terminal:

```powershell
uv run python scripts/demo/run_demo.py
```

The script gets its own token from `POST /auth/token` (subject `demo-op1`, role `field`) and then injects on 40m, relays to 2m, and polls `/transcripts`. No manual auth needed. See [scripts/demo/README.md](scripts/demo/README.md) and [docs/demo-two-local-one-remote.md](docs/demo-two-local-one-remote.md).

## Monitoring

**Prometheus:** `GET /metrics` (no auth) exposes uptime, callsign count, and optional GPU gauges (when `nvidia-smi` is available). Optional: `uv sync --extra metrics` for full prometheus-client support. See [Monitoring](https://memyself.github.io/monorepo/monitoring/) in the docs.

## Development

```bash
# Run tests
uv run pytest tests/unit tests/integration -v

# Type check
uv run mypy radioshaq

# Lint / format
uv run ruff check . && uv run ruff format .
```

## License

MIT
