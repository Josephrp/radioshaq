# Quick Start

This guide gets the RadioShaq API running on your machine in a few minutes. By the end you’ll have a local API that can run the REACT orchestrator (message processing), use the database for transcripts and callsigns, and serve the OpenAPI docs. No radio is required for this path—you can add a rig and voice pipeline later using [Configuration](configuration.md) and [Radio Usage](radio-usage.md).

**(Optional) Interactive setup:** Run `radioshaq setup` from the `radioshaq/` directory to be guided through mode, database (Docker or URL), JWT, LLM, and optional radio/memory/field settings. Radio setup includes prompts for MessageBus outbound radio replies and whether those replies use TTS. It writes `.env` and `config.yaml` to the project root and can start Docker Postgres and run migrations. See [Configuration](configuration.md#interactive-setup).

**Voice (TTS/ASR):** TTS can use **ElevenLabs** (set `ELEVENLABS_API_KEY`) or **Kokoro** (local: `uv sync --extra tts_kokoro`). ASR can use **Voxtral/Whisper** (local: `uv sync --extra audio`) or **Scribe** (ElevenLabs API). See [Configuration → TTS and Audio](configuration.md#tts-text-to-speech).

**(Optional) Full automated setup:** From the `radioshaq/` directory, run one script to install deps, create config, start Docker Postgres (and optionally Hindsight), run migrations, and install PM2 if Node is present: **Windows** — `.\infrastructure\local\setup.ps1`; **Linux/macOS** — `./infrastructure/local/setup.sh` (or `bash infrastructure/local/setup.sh`). Then start the API with `radioshaq launch pm2` or `radioshaq run-api`. Alternatively, follow the steps below.

---

## What you need

- **Python 3.11+** and **[uv](https://github.com/astral-sh/uv)** for install and run.
- **PostgreSQL** — Easiest is Docker on port 5434 (avoids clashing with a local Postgres on 5432). You can also use an existing server and set `RADIOSHAQ_DATABASE__POSTGRES_URL`.
- **Optional:** Node.js and PM2 if you want to run the API under PM2; Docker for Postgres if you don’t have it installed.

---

## Step 1: Clone and enter the app

From the RadioShaq root, go into the RadioShaq app directory:

```text
cd radioshaq
```

---

## Step 2: Install dependencies

Install the project and dev/test extras so you can run the API and tests:

```bash
--8<-- "snippets/install-sync.sh"
```

---

## Step 3: Start PostgreSQL

If you’re using Docker, start Postgres on port 5434. From the `radioshaq/` directory you can use the launch CLI (recommended):

```bash
--8<-- "snippets/launch-docker.sh"
```

Add `--hindsight` to also start the Hindsight container (semantic memory). Or start Postgres only from the repo root:

```bash
--8<-- "snippets/postgres-up.sh"
```

If you use a different host/port or URL, set `RADIOSHAQ_DATABASE__POSTGRES_URL` before running migrations and the API.

---

## Step 4: Run migrations

Create the database schema (including PostGIS and callsign tables). From repo root:

```bash
--8<-- "snippets/migrate-up.sh"
```

Or from `radioshaq/` with your env already set: `uv run alembic upgrade head`.

---

## Step 5: Start the API

From the `radioshaq/` directory, start the FastAPI server:

```bash
--8<-- "snippets/start-api.sh"
```

**Alternative — launch CLI (Docker + PM2):** To start Docker Postgres (if available) and the API under PM2 in one go, run `radioshaq launch pm2`. Add `--hindsight` to also run the Hindsight API (requires `pip install hindsight-all` or use `radioshaq launch docker --hindsight` for Hindsight in Docker). The launch commands ensure upstreams (Postgres, optional Hindsight) are started in the right order.

```bash
--8<-- "snippets/launch-pm2.sh"
```

The API will be at **http://localhost:8000**. Interactive OpenAPI docs: **http://localhost:8000/docs**. The server loads the orchestrator, agent registry, and tool registry at startup; if the database or LLM isn’t configured, some features may be limited but the API will still run.

---

## Step 6: Get a JWT and call the API

Most endpoints require a Bearer JWT. You can request a token without prior auth (development only—in production you’d gate this). Then use the token on protected routes.

**PowerShell:**

```powershell
--8<-- "snippets/auth-get-token.ps1"
```

**Bash:**

```bash
--8<-- "snippets/auth-get-token.sh"
```

Use the token in the `Authorization` header: `Bearer $TOKEN` (Bash) or `Bearer $env:TOKEN` (PowerShell). For example, call `POST /messages/process` with a JSON body `{"message": "your request"}` to run the REACT loop.

---

## What’s next

- **Configure for production** — Set [Configuration](configuration.md): `RADIOSHAQ_JWT__SECRET_KEY`, LLM provider and API key, and optionally `RADIOSHAQ_MODE`, database URL, and log level.
- **Connect a radio** — See [Radio Usage](radio-usage.md) for rig model IDs, ports, and voice TX/RX setup (IC-7300, FT-450D, RTL-SDR, HackRF).
- **Explore the API** — Use the [API Reference](api-reference.md) and the live docs at http://localhost:8000/docs to try `/auth/token`, `/messages/process`, `/transcripts`, and relay/inject endpoints.
