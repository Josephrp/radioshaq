# 📡 RadioShaq

**S**trategic **H**am **R**adio **A**utonomous **Q**uery and **K**ontrol System

A specialized AI-powered orchestrator for ham radio operations, emergency communications, and field-to-HQ coordination.

**Documentation:** [Quick Start](https://josephrp.github.io/radioshaq/quick-start/), [Configuration](https://Josephrp.github.io/RadioShaq/configuration/), [API Reference](https://Josephrp.github.io/RadioShaq/api-reference/) (published site). In-repo source: [../docs/](../docs/) (MkDocs Material).

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Install (get everything correctly)

**Prerequisites:** Python 3.11+, [uv](https://github.com/astral-sh/uv). Optional: Docker (Postgres), Node.js (PM2).

From the **radioshaq** directory:

```powershell
# One command: install deps + dev + test
uv sync --extra dev --extra test
```

**Recommended first-time setup (cross-platform):** run interactive setup from the `radioshaq/` directory to create `.env` and `config.yaml`, optionally start Docker Postgres and run migrations:

```bash
radioshaq setup
# Or minimal prompts: radioshaq setup --quick
# Or non-interactive: radioshaq setup --no-input --mode field
```

**Full automated setup (Windows):** `.\infrastructure\local\setup.ps1` installs deps, creates config, starts Docker Postgres on port 5434, runs migrations, installs PM2 if Node is present.

See the [documentation site](https://Josephrp.github.io/RadioShaq/) (Quick Start, Configuration) or **[docs/install.md](docs/install.md)** for the full install guide (prerequisites, DB, PM2, troubleshooting).

## Quick Start

```bash
# 1. Start PostgreSQL (Docker, port 5434)
cd infrastructure/local && docker compose up -d postgres && cd ../..

# 2. Run migrations (use the runner script to avoid path issues on Windows)
python infrastructure/local/run_alembic.py upgrade head

# 3. Start API
uv run python -m radioshaq.api.server
# API: http://localhost:8000/docs — open http://localhost:8000/ for the web UI (when using the PyPI package with bundled frontend)
```

See [Configuration](https://Josephrp.github.io/RadioShaq/configuration/) or [docs/database.md](docs/database.md) for DATABASE_URL and migration commands (including the `run_alembic.py` script).

**Memory (per-callsign):** Run the memory migration (`uv run alembic upgrade head`) to create memory tables. Optional [Hindsight](https://hindsight.vectorize.io/) for semantic memory: set `RADIOSHAQ_MEMORY__HINDSIGHT_BASE_URL` and install `hindsight-client` if needed; or set `RADIOSHAQ_MEMORY__HINDSIGHT_ENABLED=false` for PostgreSQL-only memory. See [../MEMORY_SYSTEM.md](../MEMORY_SYSTEM.md) and [../MEMORY_IMPLEMENTATION_PLAN.md](../MEMORY_IMPLEMENTATION_PLAN.md).

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

Roles: `field` (default), `hq`, `receiver`. Full details: [docs/auth.md](docs/auth.md). **Connecting real radios (IC-7300, FT-450D, FT-817, RTL-SDR):** see [Radio Usage](https://Josephrp.github.io/RadioShaq/radio-usage/) or [../docs/HARDWARE_CONNECTION.md](../docs/HARDWARE_CONNECTION.md) for CAT/Hamlib config and remote receiver deployment.

## Demo (inject, relay, poll)

With the API running, in a second terminal:

```powershell
uv run python scripts/demo/run_demo.py
```

The script gets its own token from `POST /auth/token` (subject `demo-op1`, role `field`) and then injects on 40m, relays to 2m, and polls `/transcripts`. No manual auth needed. See [scripts/demo/README.md](scripts/demo/README.md) and [docs/demo-two-local-one-remote.md](docs/demo-two-local-one-remote.md).

## Monitoring

**Prometheus:** `GET /metrics` (no auth) exposes uptime, callsign count, and optional GPU gauges (when `nvidia-smi` is available). Optional: `uv sync --extra metrics` for full prometheus-client support. See [Monitoring](https://Josephrp.github.io/RadioShaq/monitoring/) in the docs.

## Installing from PyPI

```bash
pip install radioshaq
radioshaq run-api
```

Then open **http://localhost:8000/** for the web UI and **http://localhost:8000/docs** for the API. The wheel includes the bundled web interface when the package is built with the frontend (see *Publishing* below).

**Remote receiver (SDR):** For listen-only stations (e.g. Raspberry Pi + RTL-SDR) that stream to HQ, run `radioshaq run-receiver` after the same install. Set `JWT_SECRET`, `STATION_ID`, `HQ_URL`; optionally `pip install radioshaq[sdr]` or `radioshaq[hackrf]` for hardware support. HQ accepts uploads at `POST /receiver/upload`.

## Development

```bash
# Run tests (memory tests use HINDSIGHT_ENABLED=false; test_manager may skip without migrated DB)
uv run pytest tests/unit tests/integration -v

# Type check
uv run mypy radioshaq

# Lint / format
uv run ruff check . && uv run ruff format .
```

## License

MIT
