# RadioShaq

**S**trategic **H**am **R**adio **A**utonomous **Q**uery and **K**ontrol System

An AI-powered orchestrator for ham radio operations, emergency communications, and field-to-HQ coordination. One install gives you the API, web UI, and optional remote SDR receiver.

---

## Install

```bash
pip install radioshaq
```

**Optional (for SDR hardware):** `pip install radioshaq[sdr]` (RTL-SDR) or `radioshaq[hackrf]` (HackRF).

**Requirements:** Python 3.11+

---

## Easiest way to get started: interactive setup

From a project directory (or the repo root), run:

```bash
radioshaq setup
```

This walks you through:

- **Mode** — field, hq, or receiver
- **Database** — use Docker Postgres or an existing URL
- **Secrets** — JWT secret, LLM API key (optional)
- **Config** — writes `.env` and `config.yaml`, can start Docker and run migrations

**Minimal prompts:** `radioshaq setup --quick` (mode + “use Docker?” then defaults).

**Non-interactive (CI/scripts):** `radioshaq setup --no-input --mode field` (optionally `--db-url postgresql://...`).

**Reconfigure:** `radioshaq setup --reconfigure` to update existing config without starting over.

---

## Run the API and web UI

```bash
radioshaq run-api
```

- **API docs:** http://localhost:8000/docs  
- **Web UI:** http://localhost:8000/  
- **Health:** http://localhost:8000/health  

Default host: `0.0.0.0`, port: `8000`. Override with `--host` and `--port`.

---

## Get a token (auth)

Most API calls need a Bearer JWT:

```bash
radioshaq token --subject op1 --role field --station-id STATION-01
```

Then set `RADIOSHAQ_TOKEN` to the printed value, or pass it in requests. Roles: `field`, `hq`, `receiver`.

**Check API from the CLI:**

```bash
radioshaq health
radioshaq health --ready
```

---

## CLI at a glance

| Command | What it does |
|--------|------------------|
| **setup** | |
| `radioshaq setup` | Interactive setup: .env, config.yaml, optional Docker and migrations |
| `radioshaq setup --quick` | Minimal prompts (mode, use Docker?), then defaults |
| `radioshaq setup --no-input --mode field` | Non-interactive for CI; optional `--db-url`, `--config-dir` |
| `radioshaq setup --reconfigure` | Update existing config (merge sections) |
| **Server & auth** | |
| `radioshaq run-api` | Start FastAPI server (and web UI at /). Options: `--host`, `--port`, `--reload` |
| `radioshaq run-receiver` | Start remote SDR receiver (port 8765). Set `JWT_SECRET`, `STATION_ID`, `HQ_URL` |
| `radioshaq token` | Get JWT. Options: `--subject`, `--role`, `--station-id`, `--base-url` |
| `radioshaq health` | Liveness check; `radioshaq health --ready` for readiness |
| **Callsigns** (require `RADIOSHAQ_TOKEN`) | |
| `radioshaq callsigns list` | List registered callsigns |
| `radioshaq callsigns add <callsign>` | Register a callsign |
| `radioshaq callsigns remove <callsign>` | Remove from whitelist |
| `radioshaq callsigns register-from-audio <file>` | Register from audio (ASR) |
| **Messages** | |
| `radioshaq message process <text>` | Send message through REACT orchestrator |
| `radioshaq message inject <text>` | Inject into RX path (demo). Options: `--band`, `--mode`, `--source-callsign` |
| `radioshaq message whitelist-request <text>` | Whitelist request (orchestrator + optional TTS) |
| `radioshaq message relay <msg> --source-band X --target-band Y` | Relay message between bands |
| **Transcripts** | |
| `radioshaq transcripts list` | List transcripts. Options: `--callsign`, `--band`, `--since`, `--limit` |
| `radioshaq transcripts get <id>` | Get one transcript |
| `radioshaq transcripts play <id>` | Play transcript as TTS over radio |
| **Radio** | |
| `radioshaq radio bands` | List bands |
| `radioshaq radio send-tts <message>` | Send TTS over radio. Options: `--frequency-hz`, `--mode` |

Use `radioshaq --help` and `radioshaq <command> --help` for options. API base URL: `RADIOSHAQ_API` (default `http://localhost:8000`).

---

## Remote receiver (SDR listen-only)

For a listen-only station (e.g. Raspberry Pi + RTL-SDR) that streams to HQ:

```bash
pip install radioshaq[sdr]   # or radioshaq[hackrf] for HackRF
export JWT_SECRET=your-secret
export STATION_ID=RECEIVER-01
export HQ_URL=http://your-hq:8000
radioshaq run-receiver
```

HQ accepts uploads at `POST /receiver/upload` (Bearer JWT). Default receiver port: `8765` (`--port` to change).

---

## After install (no interactive setup)

If you prefer to configure by hand:

1. **Database:** Set `DATABASE_URL` or `POSTGRES_*` (and run migrations with your Alembic config).
2. **Config:** Copy `config.example.yaml` to `config.yaml` and set `mode`, `database`, `auth`, etc. See [Configuration](https://Josephrp.github.io/RadioShaq/configuration/).
3. **Start:** `radioshaq run-api`.

---

## Documentation

- [Quick Start](https://Josephrp.github.io/RadioShaq/quick-start/)
- [Configuration](https://Josephrp.github.io/RadioShaq/configuration/)
- [API Reference](https://Josephrp.github.io/RadioShaq/api-reference/)
- [Radio / hardware](https://Josephrp.github.io/RadioShaq/radio-usage/)

---

## License

MIT
