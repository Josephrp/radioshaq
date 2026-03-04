# Quick Start

This guide gets the RadioShaq API running on your machine in a few minutes. By the end you’ll have a local API that can run the REACT orchestrator (message processing), use the database for transcripts and callsigns, and serve the OpenAPI docs. No radio is required for this path—you can add a rig and voice pipeline later using [Configuration](configuration.md) and [Radio Usage](radio-usage.md).

**(Optional) Interactive setup:** Run `radioshaq setup` from the `radioshaq/` directory to be guided through mode, database (Docker or URL), JWT, LLM, and optional radio/memory/field settings. It writes `.env` and `config.yaml` to the project root and can start Docker Postgres and run migrations. See [Configuration](configuration.md#interactive-setup). Alternatively, follow the steps below or use the PowerShell script (see [Interactive Setup Plan](interactive-setup-plan.md)).

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
--8<-- "docs/snippets/install-sync.sh"
```

---

## Step 3: Start PostgreSQL

If you’re using Docker, start Postgres on port 5434 from the repo root (so the default config works without changing env):

```bash
--8<-- "docs/snippets/postgres-up.sh"
```

If you use a different host/port or URL, set `RADIOSHAQ_DATABASE__POSTGRES_URL` before running migrations and the API.

---

## Step 4: Run migrations

Create the database schema (including PostGIS and callsign tables). From repo root:

```bash
--8<-- "docs/snippets/migrate-up.sh"
```

Or from `radioshaq/` with your env already set: `uv run alembic upgrade head`.

---

## Step 5: Start the API

From the `radioshaq/` directory, start the FastAPI server:

```bash
--8<-- "docs/snippets/start-api.sh"
```

The API will be at **http://localhost:8000**. Interactive OpenAPI docs: **http://localhost:8000/docs**. The server loads the orchestrator, agent registry, and tool registry at startup; if the database or LLM isn’t configured, some features may be limited but the API will still run.

---

## Step 6: Get a JWT and call the API

Most endpoints require a Bearer JWT. You can request a token without prior auth (development only—in production you’d gate this). Then use the token on protected routes.

**PowerShell:**

```powershell
--8<-- "docs/snippets/auth-get-token.ps1"
```

**Bash:**

```bash
--8<-- "docs/snippets/auth-get-token.sh"
```

Use the token in the `Authorization` header: `Bearer $TOKEN` (Bash) or `Bearer $env:TOKEN` (PowerShell). For example, call `POST /messages/process` with a JSON body `{"message": "your request"}` to run the REACT loop.

---

## What’s next

- **Configure for production** — Set [Configuration](configuration.md): `RADIOSHAQ_JWT__SECRET_KEY`, LLM provider and API key, and optionally `RADIOSHAQ_MODE`, database URL, and log level.
- **Connect a radio** — See [Radio Usage](radio-usage.md) for rig model IDs, ports, and voice TX/RX setup (IC-7300, FT-450D, RTL-SDR, HackRF).
- **Explore the API** — Use the [API Reference](api-reference.md) and the live docs at http://localhost:8000/docs to try `/auth/token`, `/messages/process`, `/transcripts`, and relay/inject endpoints.
