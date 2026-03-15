# RadioShaq

Monorepo for **RadioShaq**: AI-powered ham radio orchestration, emergency communications, and remote SDR reception. One main application (single PyPI package); Python is managed with [uv](https://github.com/astral-sh/uv).

**RadioShaq** — **S**trategic **H**am **R**adio **A**utonomous **Q**uery and **K**ontrol System — is an autonomous agent that understands natural language requests, plans steps, and delegates to specialized sub-agents and tools. It provides a FastAPI backend, React (Vite) web UI, PostgreSQL + PostGIS + Alembic, and optional real radios and SDR. The **remote receiver** (listen-only SDR station) is bundled; run it with `radioshaq run-receiver`.

---

## What’s in this repo

- **radioshaq/** — Main application (single installable package)
  - **radioshaq/** — Python package: API, REACT orchestrator, agents (radio_tx, radio_rx, radio_rx_audio, whitelist, sms, whatsapp, gis, propagation, scheduler), tools (send_audio_over_radio, relay_message_between_bands, callsign list/register), compliance (band plans, TX audit), voice pipeline (capture → VAD → ASR → MessageBus)
  - **web-interface/** — React frontend (Vite + TypeScript): Map (operator/emergency locations), Transcripts, Callsigns, Messages, Radio, Emergency, Audio config, Settings
  - **tests/** — pytest (unit + integration)
  - **infrastructure/** — Docker Compose (Postgres, optional Hindsight), PM2, Alembic, AWS Lambda
  - **scripts/** — Demos and utilities
- **docs/** — Quick start, configuration, API reference, radio usage, map configuration

---

## Features (from the implementation)

- **REACT loop** — Reasoning → Evaluation → Acting → Communicating → Tracking; Task Judge and turn/token limits
- **Modes** — `field`, `hq`, `receiver` (config-driven)
- **API** — Auth (JWT), health, messages (process, whitelist-request, inject, relay, from-audio), transcripts, callsigns (list, register, register-from-audio, contact preferences), radio (bands, status, send-tts, send-audio, propagation), GIS (location, operators-nearby, emergency-events), emergency (request, approve/reject, events stream), receiver upload, inject, internal bus, Twilio (SMS/WhatsApp), audio config, config overrides (LLM, memory), memory blocks/summaries, optional Prometheus metrics
- **Web UI** — License gate; pages: Audio config, Emergency, Callsigns, Messages, Transcripts, Radio, Map (OpenStreetMap or Google Maps, operator/emergency locations), Settings
- **Relay** — Band-to-band (and optional SMS/WhatsApp) with optional scheduled delivery and relay delivery worker
- **Compliance** — Region-based band restrictions (FCC, CEPT, etc.), band allowlist, TX audit

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

From **repo root**:

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
$env:RADIOSHAQ_TOKEN = $r.access_token
Invoke-RestMethod -Uri "http://localhost:8000/auth/me" -Headers @{ Authorization = "Bearer $env:RADIOSHAQ_TOKEN" }
```

**Bash:**

```bash
export RADIOSHAQ_TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=STATION-01" | jq -r .access_token)
curl -H "Authorization: Bearer $RADIOSHAQ_TOKEN" http://localhost:8000/auth/me
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
| `radioshaq transcripts list` | List transcripts. Options: `--callsign`, `--band`, `--since`, `--limit` |
| `radioshaq callsigns list` | List registered callsigns |
| `radioshaq callsigns add <callsign>` | Register a callsign |
| `radioshaq radio bands` | List bands |
| `radioshaq radio send-tts "message"` | Send TTS over radio |

API base URL: `RADIOSHAQ_API` (default `http://localhost:8000`). Use `radioshaq --help` and `radioshaq <command> --help` for options.

### Demo script

With the API running, in a second terminal from **radioshaq/**:

```bash
uv run python scripts/demo/run_demo.py
```

Gets a token, injects on 40m, relays to 2m, and polls `/transcripts`. See [radioshaq/scripts/demo/README.md](radioshaq/scripts/demo/README.md) and docs under `radioshaq/scripts/demo/docs/`.

### API highlights

- **Process a message:** `POST /messages/process` with JSON `{"message": "your request"}` and header `Authorization: Bearer <token>`.
- **Transcripts:** `GET /transcripts?callsign=<callsign>&band=<band>&destination_only=true`.
- **Relay:** `POST /messages/relay` with message, source_band, target_band, optional target_channel (radio/sms/whatsapp).
- **GIS:** `POST /gis/location`, `GET /gis/location/{callsign}`, `GET /gis/operators-nearby`, `GET /gis/emergency-events`.
- **Emergency:** `POST /emergency/request`, `GET /emergency/events`, `POST /emergency/events/{id}/approve` or `/reject`.
- Full OpenAPI spec at **http://localhost:8000/docs**.

---

## Run the remote receiver

From **radioshaq/** (SDR listen-only station streaming to HQ):

```bash
uv sync --extra sdr   # or --extra hackrf on non-Windows

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
| [docs/index.md](docs/index.md) | Agent overview, REACT loop, agents, tools, modes |
| [radioshaq/docs/map-configuration.md](radioshaq/docs/map-configuration.md) | Map provider (OSM/Google), tile sources |
| [radioshaq/README.md](radioshaq/README.md) | App install, auth, demo, monitoring |

---

## Project structure

```
radioshaq/                   # Main application (single PyPI package)
├── radioshaq/               # Python package (API, radio, audio, orchestrator, agents, tools)
│   └── remote_receiver/     # Bundled SDR receiver (radioshaq run-receiver)
├── web-interface/          # React frontend (Vite + TypeScript)
├── tests/                  # pytest (unit + integration)
├── infrastructure/         # Docker, PM2, AWS Lambda, Alembic
└── scripts/                # Demo and utilities

docs/                       # Quick-start, configuration, API, radio, index
.github/                    # Workflows, PYPI_README.md
```

---

## License

GPL-2.0-only
