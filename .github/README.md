# RadioShaq

Monorepo for **RadioShaq**: ham radio AI orchestration and remote SDR reception. One main app (single PyPI package); Python is managed with [uv](https://github.com/astral-sh/uv).

**What this repo does**

- **RadioShaq** — AI-powered orchestrator for ham radio, emergency comms, and field–HQ coordination. FastAPI backend, React (Vite) web UI, Postgres + Alembic, optional real radios and SDR. The **remote receiver** (SDR listen-only station) is bundled; run with `radioshaq run-receiver`.

---

## Prerequisites

- **Python 3.11+** and **[uv](https://github.com/astral-sh/uv)**
- **PostgreSQL** — Easiest is Docker on port 5434 (avoids conflict with local 5432). Or use an existing server and set `RADIOSHAQ_DATABASE__POSTGRES_URL`.
- **Optional:** Node.js + PM2 for running the API under PM2; Docker for Postgres.

---

## Launch (choose one path)

All steps below assume you are in **radioshaq/** unless noted.

### Option A: Interactive setup (recommended first time)

Guided prompts for mode, database (Docker or URL), JWT, LLM, and optional radio/memory. Writes `.env` and `config.yaml`, can start Docker and run migrations.

```bash
cd radioshaq
uv sync --all-extras
radioshaq setup
# Minimal: radioshaq setup --quick
# CI:     radioshaq setup --no-input --mode field
```

Then start the API (see Option D or manual steps below).

### Option B: Full automated setup (Windows / Linux)

One script: install deps, create config, start Docker Postgres (port 5434), run migrations, install PM2 if Node is present.

```powershell
# Windows (from radioshaq/)
.\infrastructure\local\setup.ps1
```

```bash
# Linux/macOS (from radioshaq/)
./infrastructure/local/setup.sh
```

Then start the API with `radioshaq launch pm2` or `radioshaq run-api`.

### Option C: Manual step-by-step

```bash
cd radioshaq
uv sync --all-extras

# Start Postgres (port 5434)
cd infrastructure/local && docker compose up -d postgres && cd ../..

# Migrations (from radioshaq/)
uv run alembic -c infrastructure/local/alembic.ini upgrade head

# Start API
uv run python -m radioshaq.api.server
```

From **repo root**, Postgres and migrations can be run as:

```bash
cd radioshaq/infrastructure/local && docker compose up -d postgres && cd ../../..
python radioshaq/infrastructure/local/run_alembic.py upgrade head
```

### Option D: Launch CLI (after install)

Start dependencies and API in one go:

```bash
# Postgres only (port 5434)
radioshaq launch docker
# With Hindsight (semantic memory): radioshaq launch docker --hindsight

# Postgres + API under PM2
radioshaq launch pm2
# With Hindsight: radioshaq launch pm2 --hindsight
```

Then run migrations if needed: `uv run alembic -c infrastructure/local/alembic.ini upgrade head` from `radioshaq/`.

**Endpoints:** API docs **http://localhost:8000/docs**, web UI **http://localhost:8000/**, health **http://localhost:8000/health**.

---

## Usage

### Get a JWT

Most endpoints require a Bearer JWT. Request a token (no prior auth in dev), then send it on protected routes.

**PowerShell:**

```powershell
$r = Invoke-RestMethod -Method Post -Uri "http://localhost:8000/auth/token?subject=op1&role=field&station_id=STATION-01"
$env:TOKEN = $r.access_token
Invoke-RestMethod -Uri "http://localhost:8000/auth/me" -Headers @{ Authorization = "Bearer $env:TOKEN" }
```

**Bash:**

```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=STATION-01" | jq -r .access_token)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/auth/me
```

Roles: `field`, `hq`, `receiver`. Set `RADIOSHAQ_TOKEN` to use the CLI below.

### CLI (with API running)

| Command | Description |
|--------|-------------|
| `radioshaq token --subject op1 --role field --station-id STATION-01` | Get JWT (then set `RADIOSHAQ_TOKEN`) |
| `radioshaq health` | Liveness; `radioshaq health --ready` for readiness |
| `radioshaq message process "your request"` | Send message through REACT orchestrator |
| `radioshaq message inject "text"` | Inject into RX path (demo). Options: `--band`, `--source-callsign` |
| `radioshaq message relay "msg" --source-band 40m --target-band 2m` | Relay between bands |
| `radioshaq transcripts list` | List transcripts. Options: `--callsign`, `--band`, `--destination-only` |
| `radioshaq callsigns list` | List registered callsigns |
| `radioshaq callsigns add <callsign>` | Register a callsign |

API base URL: `RADIOSHAQ_API` (default `http://localhost:8000`). Use `radioshaq --help` and `radioshaq <command> --help` for options.

### Demo script

With the API running, in a second terminal from **radioshaq/**:

```bash
uv run python scripts/demo/run_demo.py
```

Gets a token, injects on 40m, relays to 2m, and polls `/transcripts`. See [radioshaq/scripts/demo/README.md](radioshaq/scripts/demo/README.md).

### API calls

- **Process a message:** `POST /messages/process` with JSON `{"message": "your request"}` and header `Authorization: Bearer <token>`.
- **Transcripts:** `GET /transcripts?callsign=<callsign>&destination_only=true&band=<band>` for messages for you on a band.
- See **http://localhost:8000/docs** for the full OpenAPI spec.

---

## Run the remote receiver

From **radioshaq/** (SDR listen-only station streaming to HQ):

```bash
uv sync --extra dev --extra test
# With hardware: uv sync --extra sdr   # or --extra hackrf

# Set env then run
# JWT_SECRET=... STATION_ID=RECEIVER-01 HQ_URL=http://your-hq:8000
uv run radioshaq run-receiver
```

Default port **8765**. HQ accepts uploads at `POST /receiver/upload`. See [docs/](docs/) and [radioshaq/README.md](radioshaq/README.md).

---

## Development (uv)

All from **radioshaq/**:

```bash
uv run pytest tests/unit tests/integration -v
uv run mypy radioshaq
uv run ruff check . && uv run ruff format .
uv run alembic -c infrastructure/local/alembic.ini upgrade head
```

Frontend: `cd web-interface && npm install && npm run dev`.

---

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/quick-start.md](docs/quick-start.md) | Step-by-step first run |
| [docs/configuration.md](docs/configuration.md) | Config file, env vars, interactive setup |
| [docs/radio-usage.md](docs/radio-usage.md) | Rig models, CAT, hardware |
| [docs/api-reference.md](docs/api-reference.md) | API overview |
| [radioshaq/README.md](radioshaq/README.md) | App install, auth, demo, monitoring |

---

## Project structure

```
radioshaq/                   # Main application (single PyPI package)
├── radioshaq/               # Python package (API, radio, audio, orchestrator)
│   └── remote_receiver/     # Bundled SDR receiver (radioshaq run-receiver)
├── web-interface/           # React frontend (Vite + TypeScript)
├── tests/                   # pytest (unit + integration)
├── infrastructure/          # Docker, PM2, AWS Lambda, Alembic
└── scripts/                 # Demo and utilities

docs/                        # Quick-start, configuration, snippets
.github/                     # Workflows, PYPI_README.md
```

---

## License

GPL-2.0-only
