# RadioShaq

**S**trategic **H**am **R**adio **A**utonomous **Q**uery and **K**ontrol System

AI-powered orchestration for ham radio operations, emergency communications, and field-to-HQ coordination. One install provides the FastAPI backend, bundled web UI, and optional remote SDR receiver. Supports REACT-style reasoning, specialized agents (radio TX/RX, whitelist, SMS/WhatsApp, GIS, propagation), and tools for relay, TTS, and callsign registration.

---

## Install

```bash
pip install radioshaq
```

**Requirements:** Python 3.11+

**Optional extras:**

| Extra | Purpose |
|-------|---------|
| `radioshaq[sdr]` | RTL-SDR for remote listen-only receiver |
| `radioshaq[hackrf]` | HackRF for remote receiver (non-Windows) |
| `radioshaq[audio]` | Local ASR (Whisper, Voxtral) |
| `radioshaq[voice_tx]` | Play audio to rig (sounddevice, soundfile, pydub) |
| `radioshaq[voice_rx]` | Capture + VAD for voice pipeline |
| `radioshaq[tts_kokoro]` | Local TTS (Kokoro, no API key) |
| `radioshaq[metrics]` | Prometheus `/metrics` endpoint |

**License:** RadioShaq is distributed under **GPL-2.0-only**. The CLI and web UI require license acceptance before normal use (interactive prompt or `RADIOSHAQ_LICENSE_ACCEPTED=1`).

---

## Quick start

**1. Interactive setup** (recommended)

```bash
radioshaq setup
```

Guides you through mode (field / hq / receiver), database (Docker or URL), JWT secret, optional LLM API key, and radio/voice options. Writes `.env` and `config.yaml`, can start Docker Postgres and run migrations.

- `radioshaq setup --quick` — minimal prompts (mode + Docker?), then defaults  
- `radioshaq setup --no-input --mode field` — non-interactive (CI); optional `--db-url`, `--config-dir`  
- `radioshaq setup --reconfigure` — update existing config without starting over  

**2. Run API and web UI**

```bash
radioshaq run-api
```

- **API docs:** http://localhost:8000/docs  
- **Web UI:** http://localhost:8000/  
- **Health:** http://localhost:8000/health  

Default bind: `0.0.0.0:8000`. Use `--host` and `--port` to override.

**3. Get a token**

Most API calls need a Bearer JWT:

```bash
radioshaq token --subject op1 --role field --station-id STATION-01
```

Set `RADIOSHAQ_TOKEN` to the printed value. Roles: `field`, `hq`, `receiver`.

```bash
radioshaq health
radioshaq health --ready
```

---

## CLI reference

API base URL: `RADIOSHAQ_API` (default `http://localhost:8000`). Commands that call the API require `RADIOSHAQ_TOKEN` unless noted.

| Command | Description |
|---------|-------------|
| **Setup** | |
| `radioshaq setup` | Interactive setup: .env, config.yaml, optional Docker and migrations |
| `radioshaq setup --quick` | Minimal prompts |
| `radioshaq setup --no-input --mode field` | Non-interactive; optional `--db-url`, `--config-dir` |
| `radioshaq setup --reconfigure` | Update existing config |
| **Server & auth** | |
| `radioshaq run-api` | Start FastAPI server (and web UI at /). Options: `--host`, `--port`, `--reload` |
| `radioshaq run-receiver` | Start remote SDR receiver (port 8765). Set `JWT_SECRET`, `STATION_ID`, `HQ_URL` |
| `radioshaq token --subject X --role Y [--station-id Z]` | Get JWT; print `access_token` |
| `radioshaq health` | Liveness; `radioshaq health --ready` for readiness |
| **Callsigns** | |
| `radioshaq callsigns list` | List registered callsigns |
| `radioshaq callsigns add <callsign>` | Register a callsign |
| `radioshaq callsigns remove <callsign>` | Remove from registry |
| `radioshaq callsigns register-from-audio <file>` | Register from audio (ASR) |
| **Messages** | |
| `radioshaq message process "<text>"` | Send message through REACT orchestrator |
| `radioshaq message inject "<text>"` | Inject into RX path (demo). Options: `--band`, `--mode`, `--source-callsign`, `--destination-callsign` |
| `radioshaq message whitelist-request "<text>"` | Whitelist request (orchestrator; optional TTS reply) |
| `radioshaq message relay "<msg>" --source-band X --target-band Y` | Relay message between bands |
| **Transcripts** | |
| `radioshaq transcripts list` | List transcripts. Options: `--callsign`, `--band`, `--mode`, `--since`, `--limit` |
| `radioshaq transcripts get <id>` | Get one transcript |
| `radioshaq transcripts play <id>` | Play transcript as TTS over radio |
| **Radio** | |
| `radioshaq radio bands` | List bands |
| `radioshaq radio send-tts "<message>"` | Send TTS over radio. Options: `--frequency-hz`, `--mode` |
| **Config** | |
| `radioshaq config show` | Show LLM, memory, overrides from config file (keys redacted). Option: `--section llm|memory|overrides` |
| **Launch (dev)** | |
| `radioshaq launch docker` | Start Docker Compose (Postgres; optional `--hindsight`) |
| `radioshaq launch pm2` | Start Postgres + API under PM2 (optional `--hindsight`) |

Use `radioshaq --help` and `radioshaq <command> --help` for options.

---

## Remote receiver (SDR)

For a listen-only station (e.g. Raspberry Pi + RTL-SDR) that streams to HQ:

```bash
pip install radioshaq[sdr]   # or radioshaq[hackrf] for HackRF (non-Windows)
export JWT_SECRET=your-secret
export STATION_ID=RECEIVER-01
export HQ_URL=http://your-hq:8000
radioshaq run-receiver
```

HQ accepts uploads at `POST /receiver/upload` (Bearer JWT). Receiver default port: `8765` (`--port` to change).

---

## Manual configuration (no interactive setup)

1. **Database:** Set `DATABASE_URL` or `RADIOSHAQ_DATABASE__POSTGRES_URL`; run migrations with your Alembic config.  
2. **Config:** Copy `config.example.yaml` to `config.yaml` and set `mode`, `database`, `auth`, `llm`, etc.  
3. **Start:** `radioshaq run-api`.

---

## Documentation

- [Quick Start](https://radioshaq.readthedocs.io/quick-start/)
- [Configuration](https://radioshaq.readthedocs.io/configuration/)
- [API Reference](https://radioshaq.readthedocs.io/api-reference/)
- [Radio / hardware](https://radioshaq.readthedocs.io/radio-usage/)

---

## License

GPL-2.0-only
