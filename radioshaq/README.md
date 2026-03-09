# 📡 RadioShaq

**S**trategic **H**am **R**adio **A**utonomous **Q**uery and **K**ontrol System

A specialized AI-powered orchestrator for ham radio operations, emergency communications, and field-to-HQ coordination.

**Documentation:** [Quick Start](https://radioshaq.readthedocs.io/quick-start/), [Configuration](https://radioshaq.readthedocs.io/configuration/), [API Reference](https://radioshaq.readthedocs.io/api-reference/) (Read the Docs). In-repo source: [../docs/](../docs/) (MkDocs Material).

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: GPL--2.0--only](https://img.shields.io/badge/License-GPL--2.0--only-blue.svg)](../LICENSE.md)

## Install (get everything correctly)

**Prerequisites:** Python 3.11+, [uv](https://github.com/astral-sh/uv). Optional: Docker (Postgres), Node.js (PM2).

**License notice:** RadioShaq is distributed under GPL-2.0-only. Official CLI and web UI require explicit license acceptance before normal use.

From the **radioshaq** directory:

```powershell
# One command: install deps + dev + test
uv sync --extra dev --extra test
```

**Optional voice/audio:** For TTS, use **ElevenLabs** (set `ELEVENLABS_API_KEY`) or **Kokoro** (local: `uv sync --extra tts_kokoro`). For ASR, use **Voxtral/Whisper** (local: `uv sync --extra audio`) or **Scribe** (ElevenLabs API). See [Configuration](https://radioshaq.readthedocs.io/configuration/) for `tts.*` and `audio.asr_model`.

**Recommended first-time setup (cross-platform):** run interactive setup from the `radioshaq/` directory to create `.env` and `config.yaml`, optionally start Docker Postgres and run migrations:

```bash
radioshaq setup
# Or minimal prompts: radioshaq setup --quick
# Or non-interactive: radioshaq setup --no-input --mode field
```

**Full automated setup:** Run one script from the `radioshaq/` directory: Windows — `.\infrastructure\local\setup.ps1`; Linux/macOS — `./infrastructure/local/setup.sh` (or `bash infrastructure/local/setup.sh`). Each installs deps, creates config, starts Docker Postgres on port 5434 (optional Hindsight), runs migrations, and installs PM2 if Node is present.

See the [documentation site](https://radioshaq.readthedocs.io/) (Quick Start, Configuration) or **[docs/install.md](docs/install.md)** for the full install guide (prerequisites, DB, PM2, troubleshooting).

## Quick Start

```bash
# 1. Start PostgreSQL (Docker, port 5434) — or use launch CLI
radioshaq launch docker
# With Hindsight (semantic memory): radioshaq launch docker --hindsight

# Or manually: cd infrastructure/local && docker compose up -d postgres && cd ../..

# 2. Run migrations (use uv run so project deps are available; runner avoids path issues on Windows)
uv run python infrastructure/local/run_alembic.py upgrade head

# 3. Start API
uv run python -m radioshaq.api.server
# Or: radioshaq launch pm2  (starts Docker Postgres if needed, then PM2 API)
# Or with Hindsight: radioshaq launch pm2 --hindsight
# API: http://localhost:8000/docs — open http://localhost:8000/ for the web UI (when using the PyPI package with bundled frontend)
```

See [Configuration](https://radioshaq.readthedocs.io/configuration/) or [docs/database.md](docs/database.md) for DATABASE_URL and migration commands (including the `run_alembic.py` script).

**Launch (dev):** From the project root, `radioshaq launch docker` starts Postgres; `radioshaq launch docker --hindsight` adds Hindsight. Use `radioshaq launch pm2` to start Docker Postgres (if available) and the API via PM2; add `--hindsight` to also run Hindsight under PM2 (requires `pip install hindsight-all`). Configurations that need upstreams (e.g. API → Postgres, API → Hindsight) are satisfied by starting Postgres and optionally Hindsight before the API.

**Memory (per-callsign):** Run the memory migration (`uv run alembic upgrade head`) to create memory tables. Optional [Hindsight](https://hindsight.vectorize.io/) for semantic memory: set `RADIOSHAQ_MEMORY__HINDSIGHT_BASE_URL` and install `hindsight-client` if needed; or set `RADIOSHAQ_MEMORY__HINDSIGHT_ENABLED=false` for PostgreSQL-only memory. See [../MEMORY_SYSTEM.md](../MEMORY_SYSTEM.md) and [../MEMORY_IMPLEMENTATION_PLAN.md](../MEMORY_IMPLEMENTATION_PLAN.md).

### Runtime topology (API process)

When you run `python -m radioshaq.api.server` (or `radioshaq run-api`), a single process runs:

- **API** (FastAPI), **orchestrator** (REACT), and optional **MessageBus consumer** (when `RADIOSHAQ_BUS_CONSUMER_ENABLED=1`).
- **Outbound handler:** One dispatcher consumes outbound messages and routes by channel: `radio_rx` → radio TX, `sms` → Twilio SMS, `whatsapp` → Twilio WhatsApp. So SMS and WhatsApp outbound are handled inside the API process when the bus consumer is enabled; no separate Node bridge is required.
- **Optional Node bridge:** PM2 can start a `radioshaq-bridge` app only if `bridge/dist/index.js` exists; if the bridge directory is absent, that app is skipped and the API runs without it.

SMS/WhatsApp configuration: see [docs/twilio-sms-whatsapp.md](docs/twilio-sms-whatsapp.md) and `.env.example` (`RADIOSHAQ_TWILIO__*`).

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

Roles: `field` (default), `hq`, `receiver`. Full details: [docs/auth.md](docs/auth.md). **Connecting real radios (IC-7300, FT-450D, FT-817, RTL-SDR):** see [Radio Usage](https://radioshaq.readthedocs.io/radio-usage/) or [../docs/HARDWARE_CONNECTION.md](../docs/HARDWARE_CONNECTION.md) for CAT/Hamlib config and remote receiver deployment.

## Demo (inject, relay, poll)

With the API running, in a second terminal:

```powershell
uv run python scripts/demo/run_demo.py
```

The script gets its own token from `POST /auth/token` (subject `demo-op1`, role `field`) and then injects on 40m, relays to 2m, and polls `/transcripts`. No manual auth needed. To poll **your messages** on a band (messages where you are the destination), use `GET /transcripts?callsign=<your_callsign>&destination_only=true&band=<band>`; omit `band` to get messages across all bands. See [scripts/demo/README.md](scripts/demo/README.md) and [docs/demo-two-local-one-remote.md](docs/demo-two-local-one-remote.md).

## Response, compliance, and monitoring

**Response:** Operator approval of emergency SMS/WhatsApp: poll `GET /emergency/pending-count` or `GET /emergency/events` to see pending requests, then `POST /emergency/events/{id}/approve` to send (see [Response & compliance](docs/response-compliance-and-monitoring.md)). Relay (radio/SMS/WhatsApp) and contact preferences (notify-on-relay, opt-out) are documented there as well.

**Compliance:** Radio restricted bands and band plans by region (FCC, CEPT, CA, etc.); messaging consent, opt-out, and emergency region allowlist. See [docs/response-compliance-and-monitoring.md](docs/response-compliance-and-monitoring.md) (includes regulatory references, backend table, country mapping) and [notify-and-emergency-compliance-plan.md](docs/notify-and-emergency-compliance-plan.md).

**Monitoring:** `GET /metrics` (no auth) exposes uptime, callsign count, relay delivery count, and optional GPU gauges (when `nvidia-smi` is available). Optional: `uv sync --extra metrics` for full prometheus-client support. See [Response & compliance](docs/response-compliance-and-monitoring.md).

## Installing from PyPI

```bash
pip install radioshaq
radioshaq run-api
```

Then open **http://localhost:8000/** for the web UI and **http://localhost:8000/docs** for the API. The wheel includes the bundled web interface when the package is built with the frontend (see *Publishing* below).

**Remote receiver (SDR):** For listen-only stations (e.g. Raspberry Pi + RTL-SDR) that stream to HQ, run `radioshaq run-receiver` after the same install. Set `JWT_SECRET`, `STATION_ID`, `HQ_URL`; optionally `pip install radioshaq[sdr]` or `radioshaq[hackrf]` for hardware support. HQ accepts uploads at `POST /receiver/upload`.

### HackRF on Windows

The `python-hackrf` package needs the **HackRF SDK** (headers and DLLs) at build time. By default it looks for `C:\Program Files\HackRF\include\hackrf.h` and `C:\Program Files\HackRF\lib\`.

1. **Install the HackRF SDK for Windows** (pick one):
   - **Prebuilt (easiest):** Download a Windows build from [greatscottgadgets/hackrf Actions](https://github.com/greatscottgadgets/hackrf/actions) (log in, pick a successful run, download the Windows artifact). Or check [python_hackrf Releases](https://github.com/GvozdevLeonid/python_hackrf/releases) for a ZIP that contains `include/` and `lib/`.
   - **Extract** so you have:
     - `C:\Program Files\HackRF\include\hackrf.h`
     - `C:\Program Files\HackRF\lib\` with `hackrf.dll`, `hackrf.lib` (MSVC), and dependencies (e.g. `libusb-1.0.dll`, `pthreadVC2.dll`).
   - **Or build from source:** See [HackRF docs – Windows: Building From Source](https://hackrf.readthedocs.io/en/latest/installing_hackrf_software.html) (Visual Studio, CMake, vcpkg). Then copy the built `include/` and `lib/` (or `.dll`/`.lib`) into `C:\Program Files\HackRF\` or set the env vars below.

2. **Custom install path:** If you put HackRF elsewhere, set before building:
   ```powershell
   $env:PYTHON_HACKRF_INCLUDE_PATH = "C:\path\to\hackrf\include"
   $env:PYTHON_HACKRF_LIB_PATH    = "C:\path\to\hackrf\lib"
   $env:HACKRF_LIB_DIR            = "C:\path\to\hackrf\lib"
   ```

3. **Install the hackrf extra:** In this repo the `hackrf` extra is skipped on Windows by default so `uv sync --all-extras` doesn’t fail. After the SDK is in place, install the binding explicitly:
   ```powershell
   uv pip install python-hackrf
   # Or add hackrf to the project and remove the Windows-only marker in pyproject.toml, then:
   # uv sync --extra hackrf
   ```

**Driver:** For the device itself, use [Zadig](https://zadig.akeo.ie/) to install the WinUSB driver for HackRF One. Alternatively, [RadioConda](https://github.com/ryanvolz/radioconda) provides HackRF binaries and a Conda environment on Windows (use that Python/conda if you prefer).

## Development

Install dependencies first (from the **radioshaq** directory): `uv sync --extra dev --extra test`. Then use `uv run` for all commands below so the correct environment (with geoalchemy2, loguru, etc.) is used.

```bash
# Run tests (memory tests use HINDSIGHT_ENABLED=false; test_manager may skip without migrated DB)
uv run pytest tests/unit tests/integration -v

# Type check
uv run mypy radioshaq

# Lint / format
uv run ruff check . && uv run ruff format .
```

### Serving the web UI from the API (local)

To test the API serving the same UI as the built bundle (e.g. before packaging or in CI):

```bash
cd web-interface && npm run build
mkdir -p ../radioshaq/web_ui && cp -r dist/. ../radioshaq/web_ui/
cd .. && uv run python -m radioshaq.api.server
```

Then open http://localhost:8000/. CI (test-ci, publish-pypi, publish-nightly) builds the web UI and copies it to `radioshaq/radioshaq/web_ui` so the served artifact matches the source for the same commit.

### Troubleshooting: ModuleNotFoundError (geoalchemy2, loguru)

If you see `ModuleNotFoundError: No module named 'geoalchemy2'` or `...'loguru'` when running migrations, tests, or the API, the command is using a Python that doesn't have the project's dependencies. Fix:

1. From the **radioshaq** directory run: `uv sync --extra dev --extra test`
2. Run commands via **uv run** so the project venv is used, e.g.  
   `uv run python infrastructure/local/run_alembic.py upgrade head`,  
   `uv run pytest tests/unit -v`,  
   `uv run python -m radioshaq.api.server`

## License

GPL-2.0-only
