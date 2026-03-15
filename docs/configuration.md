# Configuration

RadioShaq is configured via a single **Pydantic Settings** model (`radioshaq.config.schema.Config`). You can use **environment variables**, an optional **YAML/JSON file**, or both. Environment variables override file values, so you can keep secrets in env and the rest in a file. You can also **view or overlay** LLM, memory, and per-role overrides via the **web Settings** page and the **`/api/v1/config/*`** endpoints (see [Per-role and per-subagent overrides](#per-role-and-per-subagent-overrides)); use **`radioshaq config show`** to print config from file. This page explains how configuration is loaded, how to go from zero to a running station, and documents every option.

---

## How configuration is loaded

1. **Defaults** — Every setting has a default in code (e.g. `mode: field`, `postgres_url` pointing to `127.0.0.1:5434`).
2. **Config file** — If present, `config.yaml` (or the path in `RADIOSHAQ_YAML_FILE` / your app’s config path) is loaded. Keys are nested (e.g. `database.postgres_url`, `radio.enabled`). JSON is also supported.
3. **Environment variables** — All top-level and nested settings can be set with the prefix **`RADIOSHAQ_`** and double underscore **`__`** for nesting. Examples:
   - `RADIOSHAQ_MODE=field`
   - `RADIOSHAQ_DATABASE__POSTGRES_URL=postgresql+asyncpg://user:pass@host:5432/db`
   - `RADIOSHAQ_LLM__PROVIDER=mistral`
   - `RADIOSHAQ_LLM__MISTRAL_API_KEY=your-key` (or set `MISTRAL_API_KEY`)
   - `RADIOSHAQ_RADIO__ENABLED=true`
   - `RADIOSHAQ_RADIO__RIG_MODEL=3073`
   - `RADIOSHAQ_AUDIO__RESPONSE_MODE=confirm_first`

Env wins over the file; the file wins over defaults. Use env for secrets and deployment-specific values, and the file for shared or readable structure.

---

## Example files

Two reference files (synced from `radioshaq/` into the docs by CI) provide exhaustive listings of every option:

- **[.env.example](reference/.env.example)** — Every environment variable: `RADIOSHAQ_*` (and `__` for nested keys), plus `DATABASE_URL` / `POSTGRES_*` (for Alembic), `MISTRAL_API_KEY`, `ELEVENLABS_API_KEY`, `RADIOSHAQ_BUS_CONSUMER_ENABLED`, `API_HOST`, `API_PORT`, and other runtime variables. Copy to `.env` in `radioshaq/` and set values as needed.
- **[config.example.yaml](reference/config.example.yaml)** — Full YAML configuration mirroring the schema (core, database, jwt, llm, memory, radio, audio, field, hq, pm2). Copy to `config.yaml` in `radioshaq/` (or set the path via your app’s config path). Env vars override file values.

Use these as the single source of truth for option names and env var spelling.

### Interactive setup

Run **`radioshaq setup`** from the `radioshaq/` directory (project root) to create or update `.env` and `config.yaml` via prompts:

- **First-time:** Prompts for mode, database (Docker / URL / skip), JWT secret, LLM provider and API key (optional), then optional radio, memory, field/HQ, **station callsign**, and **trigger phrases** (voice activation). In radio prompts, setup now also asks whether MessageBus-driven radio replies are enabled and whether those replies should use TTS. Writes to project root by default; use `--config-dir` to override.
- **Reconfigure:** `radioshaq setup --reconfigure` loads existing config and lets you change selected sections (mode, database, jwt, llm, memory, overrides).
- **Quick:** `radioshaq setup --quick` asks only for mode and “Use Docker for Postgres?” then uses defaults and can start Docker and run migrations.
- **CI / no-input:** `radioshaq setup --no-input --mode field [--db-url ...] [--station-callsign K5ABC] [--trigger-phrases "radioshaq, field station"] [--llm-provider mistral] [--llm-model mistral-large-latest] [--custom-api-base http://localhost:11434] [--hindsight-url http://localhost:8888] [--memory-enabled] [--radio-reply-tx-enabled|--radio-reply-tx-disabled] [--radio-reply-use-tts|--radio-reply-no-tts] [--llm-overrides '{"whitelist":{"provider":"custom","model":"ollama/llama2","custom_api_base":"http://localhost:11434"}}']` writes default files with no prompts; use in scripts or CI. **Per-role LLM:** use `--llm-overrides` with a JSON object mapping role names (`orchestrator`, `judge`, `whitelist`, `daily_summary`) to partial LLM config (e.g. `provider`, `model`, `custom_api_base`).
- **Per-role LLM (interactive):** In full setup or when using **reconfigure** and choosing **overrides**, you can configure per-role LLM overrides (orchestrator, judge, whitelist, daily_summary). Each override can set a different provider, model, and (for custom) API base; API keys remain in env. Use **reconfigure** → **overrides** to add or change them later.
- **Config show:** `radioshaq config show [--section llm|memory|overrides] [--config-dir PATH]` prints LLM, memory, and per-role overrides from `config.yaml` (API keys redacted).
- **Launch (dev):** After setup, start dependencies and the API with **`radioshaq launch docker`** (Postgres only), **`radioshaq launch docker --hindsight`** (Postgres + Hindsight), **`radioshaq launch pm2`** (Docker Postgres + PM2 API), or **`radioshaq launch pm2 --hindsight`**. These commands work on Windows, Linux, and macOS.

See [.env.example](reference/.env.example) and [config.example.yaml](reference/config.example.yaml) for all options. The full design is in the Interactive Setup Plan document (in `docs-archive/interactive-setup-plan.md`).

---

## Setup to operate: the big picture

To **set up** and **operate** a RadioShaq station you typically:

1. **Install** — Clone the repo, install dependencies (e.g. `uv sync --extra dev --extra test` in `radioshaq/`), and ensure Python 3.11+, optional Docker for Postgres, optional Node for PM2. **Full automated setup:** Run `.\infrastructure\local\setup.ps1` (Windows) or `./infrastructure/local/setup.sh` (Linux/macOS) from `radioshaq/` to install deps, create config, start Docker Postgres (optional Hindsight), run migrations, and install PM2.
2. **Database** — Run PostgreSQL (e.g. Docker on port 5434), set `RADIOSHAQ_DATABASE__POSTGRES_URL` (or use the default), run migrations (`alembic upgrade head` from `radioshaq/` or `python radioshaq/infrastructure/local/run_alembic.py upgrade head` from repo root). **Launch CLI:** From `radioshaq/`, run `radioshaq launch docker` to start Postgres only, or `radioshaq launch docker --hindsight` to start Postgres and Hindsight; then run migrations if needed.
3. **Auth** — Set `RADIOSHAQ_JWT__SECRET_KEY` to a secure value in production. Optionally adjust token expiry (`RADIOSHAQ_JWT__FIELD_TOKEN_EXPIRE_HOURS`, etc.).
4. **LLM** — Set provider and model (e.g. `RADIOSHAQ_LLM__PROVIDER=mistral`, `RADIOSHAQ_LLM__MODEL=mistral-large-latest`) and the corresponding API key. For a **local/custom** endpoint (e.g. Ollama), set `RADIOSHAQ_LLM__PROVIDER=custom`, `RADIOSHAQ_LLM__MODEL=ollama/llama2`, and `RADIOSHAQ_LLM__CUSTOM_API_BASE=http://localhost:11434`.
5. **Mode** — Set `RADIOSHAQ_MODE=field` (or `hq`, `receiver`) so the app knows whether it’s a field station, HQ, or receiver.
6. **Radio (optional)** — To attach a rig: set `RADIOSHAQ_RADIO__ENABLED=true`, `RADIOSHAQ_RADIO__RIG_MODEL` (Hamlib model ID), and `RADIOSHAQ_RADIO__PORT` (e.g. `COM3` or `/dev/ttyUSB0`). Optionally enable FLDIGI, packet, or SDR TX and set their options.
7. **Audio / voice (optional)** — For the voice_rx pipeline (listen or respond on air): set `RADIOSHAQ_RADIO__AUDIO_INPUT_ENABLED=true` and configure `audio.*` (input device, VAD, ASR, response_mode, trigger_phrases).
8. **Run** — Start the API (`uv run python -m radioshaq.api.server` or `radioshaq run-api` from `radioshaq/`). Or use **`radioshaq launch pm2`** to start Docker Postgres (if available) and the API under PM2; add **`--hindsight`** to also run the Hindsight API (or run Hindsight in Docker with `radioshaq launch docker --hindsight`). Optionally enable the MessageBus consumer with `RADIOSHAQ_BUS_CONSUMER_ENABLED=1`.
9. **Operate** — Call `POST /messages/process` with a Bearer JWT and a `message` (or `text`) body; or use the web UI / voice pipeline to interact with the agent.

The rest of this page fills in every option by section.

---

## Core (mode, debug, logging)

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `mode` | `RADIOSHAQ_MODE` | `field` | Operational mode: `field`, `hq`, or `receiver`. |
| `debug` | `RADIOSHAQ_DEBUG` | `false` | Enable debug behavior (e.g. verbose logging). |
| `log_level` | `RADIOSHAQ_LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `workspace_dir` | `RADIOSHAQ_WORKSPACE_DIR` | `~/.radioshaq` | Base workspace path (expanded). |
| `data_dir` | `RADIOSHAQ_DATA_DIR` | `~/.radioshaq/data` | Data directory (expanded). |

---

## Database

PostgreSQL (with optional PostGIS) is the primary store for transcripts, callsign registry, and GIS. The app uses an **async** URL (`postgresql+asyncpg://...`); Alembic uses a sync URL (replace `+asyncpg` with nothing or use a sync driver).

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `database.postgres_url` | `RADIOSHAQ_DATABASE__POSTGRES_URL` | `postgresql+asyncpg://radioshaq:radioshaq@127.0.0.1:5434/radioshaq` | PostgreSQL URL; asyncpg driver is auto-added if missing. |
| `database.postgres_pool_size` | `RADIOSHAQ_DATABASE__POSTGRES_POOL_SIZE` | `10` | Connection pool size. |
| `database.postgres_max_overflow` | `RADIOSHAQ_DATABASE__POSTGRES_MAX_OVERFLOW` | `20` | Max overflow connections. |
| `database.postgres_echo` | `RADIOSHAQ_DATABASE__POSTGRES_ECHO` | `false` | Log SQL statements. |
| `database.dynamodb_table_prefix` | `RADIOSHAQ_DATABASE__DYNAMODB_TABLE_PREFIX` | `radioshaq` | For serverless DynamoDB. |
| `database.dynamodb_endpoint` | `RADIOSHAQ_DATABASE__DYNAMODB_ENDPOINT` | `null` | Override DynamoDB endpoint (e.g. localstack). |
| `database.dynamodb_region` | `RADIOSHAQ_DATABASE__DYNAMODB_REGION` | `us-east-1` | AWS region for DynamoDB. |
| `database.redis_url` | `RADIOSHAQ_DATABASE__REDIS_URL` | `redis://localhost:6379/0` | Redis URL for caching/sessions (optional). |
| `database.alembic_config` | `RADIOSHAQ_DATABASE__ALEMBIC_CONFIG` | `infrastructure/local/alembic.ini` | Alembic config path. |
| `database.auto_migrate` | `RADIOSHAQ_DATABASE__AUTO_MIGRATE` | `false` | Run migrations on startup. |

**Migrations:** From `radioshaq/` with env set: `uv run alembic upgrade head`. From repo root:

```bash
# From repo root
python radioshaq/infrastructure/local/run_alembic.py upgrade head
```

See [Quick Start](quick-start.md) for credentials and troubleshooting.

---

## JWT / Auth

API endpoints expect a Bearer JWT. Tokens are issued by `POST /auth/token` (subject, role, station_id). Production must use a strong `secret_key`.

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `jwt.secret_key` | `RADIOSHAQ_JWT__SECRET_KEY` | `dev-secret-change-in-production` | Signing secret; **must** be changed in production. |
| `jwt.algorithm` | `RADIOSHAQ_JWT__ALGORITHM` | `HS256` | JWT algorithm. |
| `jwt.access_token_expire_minutes` | `RADIOSHAQ_JWT__ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token lifetime. |
| `jwt.refresh_token_expire_days` | `RADIOSHAQ_JWT__REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime. |
| `jwt.field_token_expire_hours` | `RADIOSHAQ_JWT__FIELD_TOKEN_EXPIRE_HOURS` | `24` | Field-station token lifetime. |
| `jwt.require_station_id` | `RADIOSHAQ_JWT__REQUIRE_STATION_ID` | `true` | Require `station_id` when issuing field tokens. |

---

## LLM

The orchestrator (REACT loop), judge, whitelist agent, and daily-summary cron use an LLM. Set the provider, model, and the matching API key. For **local/custom** endpoints (e.g. [Ollama](https://ollama.ai)), set `provider: custom`, `model` (e.g. `ollama/llama2` or `llama2`), and **`custom_api_base`** (e.g. `http://localhost:11434`). For **[Hugging Face Inference Providers](https://huggingface.co/docs/inference-providers)** (serverless models from Groq, Together, etc.), set `provider: huggingface`, `model` (e.g. `openai/gpt-oss-120b:groq`, `Qwen/Qwen2.5-7B-Instruct-1M`), and **`huggingface_api_key`** or `HF_TOKEN`; the client uses the HF router URL as `api_base`.

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `llm.provider` | `RADIOSHAQ_LLM__PROVIDER` | `mistral` | One of: `mistral`, `openai`, `anthropic`, `custom`, `huggingface`. |
| `llm.model` | `RADIOSHAQ_LLM__MODEL` | `mistral-large-latest` | Model name (e.g. `mistral-small-latest`, `gpt-4o`, `ollama/llama2`; for **huggingface**: `openai/gpt-oss-120b:groq`, `Qwen/Qwen2.5-7B-Instruct-1M`). |
| `llm.mistral_api_key` | `RADIOSHAQ_LLM__MISTRAL_API_KEY` | `null` | Mistral API key (or set `MISTRAL_API_KEY` if your code reads it). |
| `llm.openai_api_key` | `RADIOSHAQ_LLM__OPENAI_API_KEY` | `null` | OpenAI API key. |
| `llm.anthropic_api_key` | `RADIOSHAQ_LLM__ANTHROPIC_API_KEY` | `null` | Anthropic API key. |
| `llm.custom_api_base` | `RADIOSHAQ_LLM__CUSTOM_API_BASE` | `null` | **Custom provider base URL** (e.g. `http://localhost:11434` for Ollama). Passed to LiteLLM. |
| `llm.custom_api_key` | `RADIOSHAQ_LLM__CUSTOM_API_KEY` | `null` | Custom provider API key. |
| `llm.huggingface_api_key` | `RADIOSHAQ_LLM__HUGGINGFACE_API_KEY` | `null` | **Hugging Face** token for [Inference Providers](https://huggingface.co/docs/inference-providers) (or set `HF_TOKEN`). Token needs "Inference Providers" permission. |
| `llm.huggingface_api_base` | `RADIOSHAQ_LLM__HUGGINGFACE_API_BASE` | `null` | Optional; default `https://router.huggingface.co/v1` when provider is `huggingface`. |
| `llm.temperature` | `RADIOSHAQ_LLM__TEMPERATURE` | `0.1` | Sampling temperature (0–2). |
| `llm.max_tokens` | `RADIOSHAQ_LLM__MAX_TOKENS` | `4096` | Max tokens per response. |
| `llm.timeout_seconds` | `RADIOSHAQ_LLM__TIMEOUT_SECONDS` | `60.0` | Request timeout. |
| `llm.max_retries` | `RADIOSHAQ_LLM__MAX_RETRIES` | `3` | Retries on failure. |
| `llm.retry_delay_seconds` | `RADIOSHAQ_LLM__RETRY_DELAY_SECONDS` | `1.0` | Delay between retries. |

---

## Memory

Per-callsign memory: core blocks, recent messages, daily summaries, and optional [Hindsight](https://github.com/radioshaq/hindsight) integration for **semantic recall/reflect**. Embeddings run **inside Hindsight**; RadioShaq does not call an embedding API. Optional `hindsight_embedding_model` is passed to Hindsight if the service supports it.

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `memory.enabled` | `RADIOSHAQ_MEMORY__ENABLED` | `true` | Enable memory system (recall/reflect tools, context). |
| `memory.hindsight_base_url` | `RADIOSHAQ_MEMORY__HINDSIGHT_BASE_URL` | `http://localhost:8888` | Hindsight API base URL. |
| `memory.hindsight_enabled` | `RADIOSHAQ_MEMORY__HINDSIGHT_ENABLED` | `true` | Use Hindsight for semantic recall/reflect. |
| `memory.hindsight_embedding_model` | `RADIOSHAQ_MEMORY__HINDSIGHT_EMBEDDING_MODEL` | `null` | Optional embedding model for Hindsight (if supported). |
| `memory.recent_messages_limit` | `RADIOSHAQ_MEMORY__RECENT_MESSAGES_LIMIT` | `40` | Max recent messages included in context. |
| `memory.daily_summary_days` | `RADIOSHAQ_MEMORY__DAILY_SUMMARY_DAYS` | `7` | Days of daily summaries to include. |
| `memory.summary_timezone` | `RADIOSHAQ_MEMORY__SUMMARY_TIMEZONE` | `America/New_York` | Timezone for daily summary windows. |

---

## Per-role and per-subagent overrides

You can override **LLM** and **memory** settings per “role” or per **specialized agent**. Missing fields fall back to the global `llm` / `memory` config.

| Option | Description |
|--------|-------------|
| `llm_overrides` | Optional map: role or agent name → partial `LLMConfig`. Keys: `orchestrator`, `judge`, `whitelist`, `daily_summary`, or **any agent name** (e.g. `whitelist`, `gis`, `radio_tx`, `scheduler`). Only the **whitelist** agent uses an LLM today; other agent keys apply when/if that agent gets an LLM. |
| `memory_overrides` | Optional map: role → partial `MemoryConfig`. Keys: e.g. `orchestrator`, `memory`. |

**Example** (in `config.yaml`):

```yaml
llm_overrides:
  whitelist:                      # WhitelistAgent (per-subagent)
    provider: custom
    model: ollama/llama2
    custom_api_base: "http://localhost:11434"
  daily_summary:
    model: mistral-small-latest
memory_overrides:
  memory:
    hindsight_base_url: "http://hindsight-alt:8888"
```

**Where to change at runtime:**

- **Web UI** — **Settings** page: view/edit LLM, memory, and overrides (runtime overlay; does not persist to file).
- **API** — `GET`/`PATCH` `/api/v1/config/llm`, `/api/v1/config/memory`, `/api/v1/config/overrides` (see [API Reference](api-reference.md)); PATCH is runtime-only unless you add file persistence.

---

## Radio

Controls the physical rig (CAT), optional FLDIGI, packet, and SDR TX. If `radio.enabled` is false, the rig manager is not created and radio_tx/radio_rx agents run without hardware.

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `radio.enabled` | `RADIOSHAQ_RADIO__ENABLED` | `false` | Master switch for CAT/rig. |
| `radio.rig_model` | `RADIOSHAQ_RADIO__RIG_MODEL` | `1` | Hamlib rig model number (e.g. 3073 = IC-7300, 127 = FT-450D). |
| `radio.port` | `RADIOSHAQ_RADIO__PORT` | `/dev/ttyUSB0` | Serial port (e.g. `COM3`, `/dev/ttyUSB0`). |
| `radio.baudrate` | `RADIOSHAQ_RADIO__BAUDRATE` | `9600` | Serial baud rate. |
| `radio.use_daemon` | `RADIOSHAQ_RADIO__USE_DAEMON` | `false` | Use rigctld daemon instead of direct serial. |
| `radio.daemon_host` | `RADIOSHAQ_RADIO__DAEMON_HOST` | `localhost` | rigctld host. |
| `radio.daemon_port` | `RADIOSHAQ_RADIO__DAEMON_PORT` | `4532` | rigctld port. |
| `radio.fldigi_enabled` | `RADIOSHAQ_RADIO__FLDIGI_ENABLED` | `false` | Enable FLDIGI for digital modes. |
| `radio.fldigi_host` | `RADIOSHAQ_RADIO__FLDIGI_HOST` | `localhost` | FLDIGI server host. |
| `radio.fldigi_port` | `RADIOSHAQ_RADIO__FLDIGI_PORT` | `7362` | FLDIGI server port. |
| `radio.packet_enabled` | `RADIOSHAQ_RADIO__PACKET_ENABLED` | `false` | Enable packet (KISS TNC). |
| `radio.packet_callsign` | `RADIOSHAQ_RADIO__PACKET_CALLSIGN` | `N0CALL` | Packet callsign. |
| `radio.packet_ssid` | `RADIOSHAQ_RADIO__PACKET_SSID` | `0` | Packet SSID (0–15). |
| `radio.packet_kiss_host` | `RADIOSHAQ_RADIO__PACKET_KISS_HOST` | `localhost` | KISS TNC host. |
| `radio.packet_kiss_port` | `RADIOSHAQ_RADIO__PACKET_KISS_PORT` | `8001` | KISS TNC port. |
| `radio.tx_enabled` | `RADIOSHAQ_RADIO__TX_ENABLED` | `true` | Allow transmit. |
| `radio.rx_enabled` | `RADIOSHAQ_RADIO__RX_ENABLED` | `true` | Allow receive. |
| `radio.max_power_watts` | `RADIOSHAQ_RADIO__MAX_POWER_WATTS` | `100.0` | Max power (informational). |
| `radio.audio_output_device` | `RADIOSHAQ_RADIO__AUDIO_OUTPUT_DEVICE` | `null` | Sound device name/index feeding rig line-in (voice TX). |
| `radio.voice_use_tts` | `RADIOSHAQ_RADIO__VOICE_USE_TTS` | `false` | Use TTS when no audio file is provided. |
| `radio.radio_reply_tx_enabled` | `RADIOSHAQ_RADIO__RADIO_REPLY_TX_ENABLED` | `true` | Enable MessageBus outbound radio replies (`radio_rx` -> `radio_tx`). |
| `radio.radio_reply_use_tts` | `RADIOSHAQ_RADIO__RADIO_REPLY_USE_TTS` | `true` | For MessageBus outbound radio replies, force `use_tts` on/off. |
| `radio.tx_audit_log_path` | `RADIOSHAQ_RADIO__TX_AUDIT_LOG_PATH` | `null` | Path to JSONL file for TX audit log. |
| `radio.tx_allowed_bands_only` | `RADIOSHAQ_RADIO__TX_ALLOWED_BANDS_ONLY` | `true` | Restrict TX to band_plan bands. |
| `radio.restricted_bands_region` | `RADIOSHAQ_RADIO__RESTRICTED_BANDS_REGION` | `FCC` | Country/region for restricted-band enforcement: `FCC`, `CA`, `CEPT`, `FR`, `UK`, `ES`, `BE`, `CH`, `LU`, `MC`, `MX`, `AR`, `CL`, … (Americas), `AU`, `ZA`, `NG`, `KE`, … (Africa), `NZ`, `JP`, `IN`. **Do not use `ITU_R1` or `ITU_R3`** here — they are band-plan-only (no restricted bands); use `band_plan_region` for those. |
| `radio.band_plan_region` | `RADIOSHAQ_RADIO__BAND_PLAN_REGION` | `null` | Override band plan source (e.g. `ITU_R1`, `ITU_R3`). If null, uses the backend from `restricted_bands_region`. Use this for ITU region plans; keep `restricted_bands_region` as a country. |
| `radio.allowed_callsigns` | (list in YAML) | `null` | Static list of allowed callsigns; merged with DB registry. |
| `radio.callsign_registry_required` | `RADIOSHAQ_RADIO__CALLSIGN_REGISTRY_REQUIRED` | `false` | If true, only registered or allowed callsigns for store/relay. |
| `radio.sdr_tx_enabled` | `RADIOSHAQ_RADIO__SDR_TX_ENABLED` | `false` | Enable HackRF (or other SDR) TX. |
| `radio.sdr_tx_backend` | `RADIOSHAQ_RADIO__SDR_TX_BACKEND` | `hackrf` | SDR backend name. |
| `radio.sdr_tx_device_index` | `RADIOSHAQ_RADIO__SDR_TX_DEVICE_INDEX` | `0` | HackRF device index. |
| `radio.sdr_tx_serial` | `RADIOSHAQ_RADIO__SDR_TX_SERIAL` | `null` | HackRF serial (optional). |
| `radio.sdr_tx_max_gain` | `RADIOSHAQ_RADIO__SDR_TX_MAX_GAIN` | `47` | Max TX gain (0–47). |
| `radio.sdr_tx_allow_bands_only` | `RADIOSHAQ_RADIO__SDR_TX_ALLOW_BANDS_ONLY` | `true` | Restrict SDR TX to allowed bands. |
| `radio.audio_input_enabled` | `RADIOSHAQ_RADIO__AUDIO_INPUT_ENABLED` | `false` | Enable voice_rx pipeline (capture from rig). |
| `radio.audio_output_enabled` | `RADIOSHAQ_RADIO__AUDIO_OUTPUT_ENABLED` | `false` | Enable audio output to rig. |
| `radio.audio_monitoring_enabled` | `RADIOSHAQ_RADIO__AUDIO_MONITORING_ENABLED` | `false` | Enable monitoring path. |
| `radio.voice_listener_enabled` | `RADIOSHAQ_RADIO__VOICE_LISTENER_ENABLED` | `true` | When true and audio_input_enabled, run voice listener so rig audio is captured, transcribed, and published to the message queue (default capture path for orchestrator/relay). |
| `radio.voice_listener_cycle_seconds` | `RADIOSHAQ_RADIO__VOICE_LISTENER_CYCLE_SECONDS` | `3600.0` | Duration (seconds) per voice monitor cycle; clamped 60–86400. |
| `radio.voice_store_transcript` | `RADIOSHAQ_RADIO__VOICE_STORE_TRANSCRIPT` | `false` | When true, store each voice segment as a transcript (metadata band, source=voice_listener) for GET /transcripts and relay. |
| `radio.default_band` | `RADIOSHAQ_RADIO__DEFAULT_BAND` | `null` | Default band when listen_bands is not set (e.g. `40m`, `2m`). |
| `radio.listen_bands` | (list in YAML) | `null` | Bands to monitor (e.g. `[40m, 2m]`). If null, only default_band is used when set. |
| `radio.listener_enabled` | `RADIOSHAQ_RADIO__LISTENER_ENABLED` | `false` | Run the background band listener when bands are configured. |
| `radio.listener_cycle_seconds` | `RADIOSHAQ_RADIO__LISTENER_CYCLE_SECONDS` | `30.0` | Seconds per band in round-robin mode (single receiver). Clamped 5–300. |
| `radio.listener_concurrent_bands` | `RADIOSHAQ_RADIO__LISTENER_CONCURRENT_BANDS` | `true` | If true, one monitor task per band in parallel; if false, single receiver round-robin. |
| `radio.relay_inject_target_band` | `RADIOSHAQ_RADIO__RELAY_INJECT_TARGET_BAND` | `false` | When relaying (no deliver_at), inject the relayed message into the target band RX queue. |
| `radio.relay_tx_target_band` | `RADIOSHAQ_RADIO__RELAY_TX_TARGET_BAND` | `false` | When relaying (no deliver_at), transmit the relayed message on the target band via radio_tx. |

**Relay:** Relay is **store-only by default**. Recipients get messages by **polling** `GET /transcripts?callsign=<their_callsign>&destination_only=true&band=<target_band>`. When `relay_inject_target_band` or `relay_tx_target_band` is enabled, they apply to both the API and the orchestrator relay tool.

**Compliance and region support:** TX is checked against restricted bands and (when `tx_allowed_bands_only` is true) the effective band plan. The **compliance plugin** provides region-specific backends:

| Backend key | Restricted bands | Band plan | Typical use |
|-------------|------------------|-----------|--------------|
| `FCC` | US 47 CFR §15.205 | Default (ITU R2) | United States |
| `CA` | FCC baseline (ISED/RBR-4) | Default (ITU R2) | Canada |
| `CEPT` | EU harmonised (ERC 70-03, ETSI) | IARU R1 (2m 144–146 MHz, 70cm 430–440 MHz) | EU general |
| `FR` | Same as CEPT | Same as CEPT | France |
| `UK` | Same as CEPT | Same as CEPT | United Kingdom |
| `ES` | Same as CEPT | Same as CEPT | Spain |
| `BE` | Same as CEPT | Same as CEPT | Belgium |
| `CH` | Same as CEPT | Same as CEPT | Switzerland |
| `LU` | Same as CEPT | Same as CEPT | Luxembourg |
| `MC` | Same as CEPT | Same as CEPT | Monaco |
| `ITU_R1` | None (band-plan only) | IARU R1 | Override band plan only |
| `ITU_R3` | None (band-plan only) | IARU R3 (2m 144–148, 70cm 430–440 MHz) | Override band plan for Asia–Pacific |
| `MX` | FCC baseline (IFT may vary) | Default (ITU R2) | Mexico |
| `AR`, `CL`, `CO`, `PE`, `VE`, `EC`, `UY`, `PY`, `BO`, `CR`, `PA`, `GT`, `DO` | FCC baseline | Default (ITU R2) | Argentina, Chile, Colombia, Peru, Venezuela, Ecuador, Uruguay, Paraguay, Bolivia, Costa Rica, Panama, Guatemala, Dominican Republic |
| `AU` | Enforced (ACMA conservative) | IARU R3 | Australia |
| `ZA` | Enforced (ICASA NRFP) | IARU R1 | South Africa |
| `NG`, `KE`, `EG`, `MA`, … (see [Response & compliance](response-compliance-and-monitoring.md#21-radio-restricted-bands-and-band-plans)) | Enforced (R1 conservative) | IARU R1 | Nigeria, Kenya, Egypt, Morocco, etc. |
| `NZ` | Enforced (RSM PIB 21 conservative) | IARU R3 | New Zealand |
| `JP` | Enforced (conservative set) | IARU R3 | Japan |
| `IN` | Enforced (conservative set) | IARU R3 | India |

Set `restricted_bands_region: CEPT` (or `FR`, `UK`, `ES`, `BE`, `CH`, `LU`, `MC`) for EU/EEA to enforce CEPT-style restricted bands and R1 band edges. For Americas use `CA`, `MX`, or country code (`AR`, `CL`, etc.). For Australia/Asia–Pacific use `AU` or `ITU_R3`. For Africa use country code (`ZA`, `NG`, `KE`, etc.) — R1 band plan, national rules apply. Use `band_plan_region: ITU_R1` or `ITU_R3` to override band plan. See [Response & compliance](response-compliance-and-monitoring.md#21-radio-restricted-bands-and-band-plans) for official sources and country→backend mapping. Operators must verify national rules (e.g. ANFR, Ofcom, ACMA, IFT, ISED, ICASA, NCC).

---

## TTS (text-to-speech)

When `radio.voice_use_tts` is true or a task sets `use_tts: true`, speech is generated from text using the configured TTS provider. Options live under `tts.*`.

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `tts.provider` | `RADIOSHAQ_TTS__PROVIDER` | `elevenlabs` | `elevenlabs` (API; set `ELEVENLABS_API_KEY`) or `kokoro` (local; run `uv sync --extra tts_kokoro`). |
| `tts.elevenlabs_voice_id` | `RADIOSHAQ_TTS__ELEVENLABS_VOICE_ID` | (Rachel) | ElevenLabs voice ID. |
| `tts.elevenlabs_model_id` | `RADIOSHAQ_TTS__ELEVENLABS_MODEL_ID` | `eleven_multilingual_v2` | ElevenLabs model (e.g. `eleven_turbo_v2_5`, `eleven_flash_v2_5`). |
| `tts.elevenlabs_output_format` | `RADIOSHAQ_TTS__ELEVENLABS_OUTPUT_FORMAT` | `mp3_44100_128` | Output format. |
| `tts.kokoro_voice` | `RADIOSHAQ_TTS__KOKORO_VOICE` | `af_heart` | Kokoro voice name (e.g. `am_michael`, `bf_emma`). |
| `tts.kokoro_lang_code` | `RADIOSHAQ_TTS__KOKORO_LANG_CODE` | `a` | Language code: `a` (US English), `b` (UK English), `e`, `f`, etc. |
| `tts.kokoro_speed` | `RADIOSHAQ_TTS__KOKORO_SPEED` | `1.0` | Speech rate (0.5–2.0). |

**Kokoro (local TTS):** Install with `uv sync --extra tts_kokoro`. This pulls in `kokoro`, `soundfile`, and Kokoro’s own dependencies (e.g. `torch`, `transformers`, `misaki[en]`). On Linux, the `soundfile` package may require the system library **libsndfile** (e.g. `apt install libsndfile1` or `dnf install libsndfile`).

---

## Audio (voice_rx pipeline)

When `radio.audio_input_enabled` is true, the voice_rx pipeline captures audio from the rig, runs VAD and ASR, applies trigger/phrase filtering, and optionally queues a response for human approval or auto-responds. These settings live under `audio.*`.

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `audio.input_device` | `RADIOSHAQ_AUDIO__INPUT_DEVICE` | `null` | Audio input device (rig line-out). |
| `audio.input_sample_rate` | `RADIOSHAQ_AUDIO__INPUT_SAMPLE_RATE` | `16000` | Sample rate (Hz). |
| `audio.output_device` | `RADIOSHAQ_AUDIO__OUTPUT_DEVICE` | `null` | Audio output device (e.g. rig line-in). |
| `audio.preprocessing_enabled` | `RADIOSHAQ_AUDIO__PREPROCESSING_ENABLED` | `true` | Enable preprocessing. |
| `audio.agc_enabled` | `RADIOSHAQ_AUDIO__AGC_ENABLED` | `true` | Automatic gain control. |
| `audio.agc_target_rms` | `RADIOSHAQ_AUDIO__AGC_TARGET_RMS` | `0.1` | AGC target RMS. |
| `audio.highpass_filter_enabled` | `RADIOSHAQ_AUDIO__HIGHPASS_FILTER_ENABLED` | `true` | High-pass filter. |
| `audio.highpass_cutoff_hz` | `RADIOSHAQ_AUDIO__HIGHPASS_CUTOFF_HZ` | `80.0` | High-pass cutoff (Hz). |
| `audio.denoising_enabled` | `RADIOSHAQ_AUDIO__DENOISING_ENABLED` | `true` | Denoising. |
| `audio.denoising_backend` | `RADIOSHAQ_AUDIO__DENOISING_BACKEND` | `rnnoise` | `rnnoise`, `spectral`, or `none`. |
| `audio.noise_calibration_seconds` | `RADIOSHAQ_AUDIO__NOISE_CALIBRATION_SECONDS` | `3.0` | Noise calibration duration. |
| `audio.min_snr_db` | `RADIOSHAQ_AUDIO__MIN_SNR_DB` | `3.0` | Minimum SNR (dB). |
| `audio.vad_enabled` | `RADIOSHAQ_AUDIO__VAD_ENABLED` | `true` | Voice activity detection. |
| `audio.vad_threshold` | `RADIOSHAQ_AUDIO__VAD_THRESHOLD` | `0.02` | VAD threshold. |
| `audio.vad_mode` | `RADIOSHAQ_AUDIO__VAD_MODE` | `aggressive` | `normal`, `low`, `aggressive`, `very_aggressive`. |
| `audio.pre_speech_buffer_ms` | `RADIOSHAQ_AUDIO__PRE_SPEECH_BUFFER_MS` | `300` | Ms of audio before speech start. |
| `audio.post_speech_buffer_ms` | `RADIOSHAQ_AUDIO__POST_SPEECH_BUFFER_MS` | `400` | Ms of audio after speech end. |
| `audio.min_speech_duration_ms` | `RADIOSHAQ_AUDIO__MIN_SPEECH_DURATION_MS` | `500` | Min segment length. |
| `audio.max_speech_duration_ms` | `RADIOSHAQ_AUDIO__MAX_SPEECH_DURATION_MS` | `30000` | Max segment length. |
| `audio.silence_duration_ms` | `RADIOSHAQ_AUDIO__SILENCE_DURATION_MS` | `800` | Silence to end segment. |
| `audio.asr_model` | `RADIOSHAQ_AUDIO__ASR_MODEL` | `voxtral` | ASR backend: `voxtral`, `whisper` (local; install with `uv sync --extra audio`), or `scribe` (ElevenLabs API; set `ELEVENLABS_API_KEY`). |
| `audio.asr_language` | `RADIOSHAQ_AUDIO__ASR_LANGUAGE` | `en` | ASR language (`en`, `fr`, `es`, or `auto`). |
| `audio.asr_min_confidence` | `RADIOSHAQ_AUDIO__ASR_MIN_CONFIDENCE` | `0.6` | Min ASR confidence (0–1). |
| `audio.response_mode` | `RADIOSHAQ_AUDIO__RESPONSE_MODE` | `listen_only` | `listen_only`, `confirm_first`, `auto_respond`, `confirm_timeout`. |
| `audio.response_timeout_seconds` | `RADIOSHAQ_AUDIO__RESPONSE_TIMEOUT_SECONDS` | `30.0` | Timeout for confirm_timeout mode. |
| `audio.response_delay_ms` | `RADIOSHAQ_AUDIO__RESPONSE_DELAY_MS` | `500` | Delay before sending response. |
| `audio.response_cooldown_seconds` | `RADIOSHAQ_AUDIO__RESPONSE_COOLDOWN_SECONDS` | `5.0` | Cooldown between responses. |
| `audio.trigger_enabled` | `RADIOSHAQ_AUDIO__TRIGGER_ENABLED` | `true` | Only process when trigger phrase detected. |
| `audio.trigger_phrases` | (list in YAML) | `["radioshaq", "field station"]` | Phrases that trigger processing. |
| `audio.trigger_match_mode` | `RADIOSHAQ_AUDIO__TRIGGER_MATCH_MODE` | `contains` | `exact`, `contains`, `starts_with`, `fuzzy`. |
| `audio.trigger_callsign` | `RADIOSHAQ_AUDIO__TRIGGER_CALLSIGN` | `null` | Optional callsign filter. |
| `audio.trigger_min_confidence` | `RADIOSHAQ_AUDIO__TRIGGER_MIN_CONFIDENCE` | `0.7` | Min confidence for trigger match. |
| `audio.audio_activation_enabled` | `RADIOSHAQ_AUDIO__AUDIO_ACTIVATION_ENABLED` | `false` | Require activation phrase before processing. |
| `audio.audio_activation_phrase` | `RADIOSHAQ_AUDIO__AUDIO_ACTIVATION_PHRASE` | `radioshaq` | Phrase to activate session. |
| `audio.audio_activation_mode` | `RADIOSHAQ_AUDIO__AUDIO_ACTIVATION_MODE` | `session` | `session` (once) or `per_message`. |
| `audio.ptt_coordination_enabled` | `RADIOSHAQ_AUDIO__PTT_COORDINATION_ENABLED` | `true` | PTT coordination for half-duplex. |
| `audio.ptt_cooldown_ms` | `RADIOSHAQ_AUDIO__PTT_COOLDOWN_MS` | `500` | PTT cooldown (ms). |
| `audio.break_in_enabled` | `RADIOSHAQ_AUDIO__BREAK_IN_ENABLED` | `true` | Allow break-in. |

**Response modes:**  
- **listen_only** — Transcribe only; no TX.  
- **confirm_first** — Queue proposed response for human approval.  
- **auto_respond** — Send response automatically (use with caution).  
- **confirm_timeout** — Auto-send after a timeout if not rejected.

---

## Field mode

When `mode: field`, these options apply (HQ connection and sync).

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `field.station_id` | `RADIOSHAQ_FIELD__STATION_ID` | `FIELD-01` | Unique field station ID. |
| `field.callsign` | `RADIOSHAQ_FIELD__CALLSIGN` | `null` | Optional callsign. |
| `field.hq_base_url` | `RADIOSHAQ_FIELD__HQ_BASE_URL` | `https://hq.radioshaq.example.com` | HQ API base URL. |
| `field.hq_ws_url` | `RADIOSHAQ_FIELD__HQ_WS_URL` | (derived) | WebSocket URL (default from base). |
| `field.hq_auth_token` | `RADIOSHAQ_FIELD__HQ_AUTH_TOKEN` | `null` | Token for HQ API. |
| `field.sync_interval_seconds` | `RADIOSHAQ_FIELD__SYNC_INTERVAL_SECONDS` | `60` | Sync interval to HQ. |
| `field.sync_batch_size` | `RADIOSHAQ_FIELD__SYNC_BATCH_SIZE` | `100` | Batch size for sync. |
| `field.sync_max_retries` | `RADIOSHAQ_FIELD__SYNC_MAX_RETRIES` | `5` | Max sync retries. |
| `field.sync_retry_delay` | `RADIOSHAQ_FIELD__SYNC_RETRY_DELAY` | `10` | Delay between retries (s). |
| `field.sync_on_connect` | `RADIOSHAQ_FIELD__SYNC_ON_CONNECT` | `true` | Sync on connect. |
| `field.offline_mode` | `RADIOSHAQ_FIELD__OFFLINE_MODE` | `false` | Disable HQ sync. |
| `field.max_offline_queue_size` | `RADIOSHAQ_FIELD__MAX_OFFLINE_QUEUE_SIZE` | `1000` | Max queued items when offline. |

---

## HQ mode

When `mode: hq`, these options apply.

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `hq.host` | `RADIOSHAQ_HQ__HOST` | `0.0.0.0` | Bind host. |
| `hq.port` | `RADIOSHAQ_HQ__PORT` | `8000` | Bind port (overridden by `API_HOST`/`API_PORT` or `RADIOSHAQ_API_HOST`/`RADIOSHAQ_API_PORT` at runtime). |
| `hq.ws_enabled` | `RADIOSHAQ_HQ__WS_ENABLED` | `true` | Enable WebSocket. |
| `hq.ws_path` | `RADIOSHAQ_HQ__WS_PATH` | `/ws` | WebSocket path. |
| `hq.max_field_stations` | `RADIOSHAQ_HQ__MAX_FIELD_STATIONS` | `100` | Max field stations. |
| `hq.field_auth_required` | `RADIOSHAQ_HQ__FIELD_AUTH_REQUIRED` | `true` | Require auth for field. |
| `hq.field_registration_open` | `RADIOSHAQ_HQ__FIELD_REGISTRATION_OPEN` | `false` | Allow field registration. |
| `hq.auto_coordination_enabled` | `RADIOSHAQ_HQ__AUTO_COORDINATION_ENABLED` | `true` | Auto coordination. |
| `hq.coordination_interval_seconds` | `RADIOSHAQ_HQ__COORDINATION_INTERVAL_SECONDS` | `30` | Coordination interval. |

---

## Twilio (SMS & WhatsApp)

RadioShaq can send and receive **SMS** and **WhatsApp** messages via **Twilio** (same account for both). Outbound delivery is handled by the single outbound dispatcher when the MessageBus consumer is enabled.

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `twilio.account_sid` | `RADIOSHAQ_TWILIO__ACCOUNT_SID` | `null` | Twilio Account SID (required for SMS and WhatsApp send). |
| `twilio.auth_token` | `RADIOSHAQ_TWILIO__AUTH_TOKEN` | `null` | Twilio Auth Token. |
| `twilio.from_number` | `RADIOSHAQ_TWILIO__FROM_NUMBER` | `null` | SMS sender phone number (E.164, e.g. `+15551234567`). |
| `twilio.whatsapp_from` | `RADIOSHAQ_TWILIO__WHATSAPP_FROM` | `null` | WhatsApp sender number (E.164); must be WhatsApp-enabled in Twilio. Optional; if unset, the WhatsApp agent is registered but returns "not configured" on send. |

All use the **`RADIOSHAQ_TWILIO__`** prefix. See [reference/.env.example](reference/.env.example) for a commented template.

**Config file (YAML):** You can set the same under `twilio` in `config.yaml`:

```yaml
twilio:
  account_sid: "ACxxxx"
  auth_token: "your-auth-token"
  from_number: "+15551234567"
  whatsapp_from: "+15551234567"   # optional; same or different number enabled for WhatsApp
```

Environment variables override file values.

**Behavior:**

- **SMS:** If `account_sid`, `auth_token`, and `from_number` are set, the SMS agent sends via Twilio. Otherwise, send returns `success: false` with `reason: "twilio_not_configured"`.
- **WhatsApp:** If `whatsapp_from` is also set (and Twilio client exists), the WhatsApp agent sends via Twilio WhatsApp Business API (`whatsapp:+E.164`). Otherwise, the agent is still registered but returns "Twilio WhatsApp not configured" on send.
- **Inbound:** Configure Twilio webhooks (SMS and/or WhatsApp) to POST to your Lambda or directly to `https://<your-hq>/internal/bus/inbound` with a body like `{"channel": "sms"|"whatsapp", "chat_id": "<sender_phone>", "sender_id": "...", "content": "..."}`. See [Twilio WhatsApp webhooks](https://www.twilio.com/docs/sms/whatsapp/api#configuring-inbound-message-webhooks) and opt-in requirements.

**Notify when a message is left for you (§8.1, §8.3):** Whitelisted callsigns can opt in to receive a short SMS or WhatsApp notification when a message is delivered to them on radio (notify-on-relay). Set contact preferences via `GET`/`PATCH /callsigns/registered/{callsign}/contact-preferences`; in strict regions (e.g. EU/UK/ZA), `consent_confirmed: true` is required when enabling. Recipients can reply **STOP** to opt out; configure your Twilio webhook (or Lambda) to call `POST /internal/opt-out` with `{"phone": "+1234567890", "channel": "sms"}` or `{"callsign": "K5ABC", "channel": "whatsapp"}`. See [Response & compliance](response-compliance-and-monitoring.md) and the project doc *Notify and emergency compliance plan* (in `radioshaq/docs/`) for region-specific consent and opt-out rules.

**References:** [Twilio WhatsApp API overview](https://www.twilio.com/docs/sms/whatsapp/api), [Twilio WhatsApp quickstart (Python)](https://www.twilio.com/docs/whatsapp/quickstart/python), [WhatsApp opt-in requirements](https://www.twilio.com/docs/sms/whatsapp/api#whatsapp-opt-in-requirements) (required for production).

---

## PM2 (process manager)

Used when running under PM2 (e.g. `ecosystem.config.js`). Log and process settings.

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `pm2.instances` | `RADIOSHAQ_PM2__INSTANCES` | `1` | Number of instances. |
| `pm2.autorestart` | `RADIOSHAQ_PM2__AUTORESTART` | `true` | Auto restart. |
| `pm2.watch` | `RADIOSHAQ_PM2__WATCH` | `true` | Watch files. |
| `pm2.max_memory_restart` | `RADIOSHAQ_PM2__MAX_MEMORY_RESTART` | `1G` | Restart if memory exceeds. |
| `pm2.log_dir` | `RADIOSHAQ_PM2__LOG_DIR` | `logs` | Log directory. |
| `pm2.log_date_format` | `RADIOSHAQ_PM2__LOG_DATE_FORMAT` | `YYYY-MM-DD HH:mm:ss Z` | Log date format. |
| `pm2.merge_logs` | `RADIOSHAQ_PM2__MERGE_LOGS` | `false` | Merge logs. |
| `pm2.env_file` | `RADIOSHAQ_PM2__ENV_FILE` | `.env` | Env file. |
| `pm2.source_map_support` | `RADIOSHAQ_PM2__SOURCE_MAP_SUPPORT` | `true` | Enable source map support. |

---

## Other runtime behavior

- **MessageBus consumer** — The API can run an inbound message consumer in the background so external systems can push work into the REACT loop. Set **`RADIOSHAQ_BUS_CONSUMER_ENABLED=1`** (or `true`/`yes`) to enable it. If not set, the consumer is disabled.
- **API host/port** — The server uses `API_HOST` / `API_PORT` or **`RADIOSHAQ_API_HOST`** / **`RADIOSHAQ_API_PORT`** when starting uvicorn (default from `hq.host` and `hq.port`).
- **CLI** — Scripts that call the API use **`RADIOSHAQ_API`** (base URL, default `http://localhost:8000`) and **`RADIOSHAQ_TOKEN`** (Bearer token).
- **TTS** — When `radio.voice_use_tts` is true (or when a task sets `use_tts: true`), speech is generated per **`tts.provider`**: **`elevenlabs`** (set **`ELEVENLABS_API_KEY`**) or **`kokoro`** (local; `uv sync --extra tts_kokoro`). See [TTS (text-to-speech)](#tts-text-to-speech).
- **ASR** — Voice pipeline and audio upload use **`audio.asr_model`**: **`voxtral`** / **`whisper`** (local; `uv sync --extra audio`) or **`scribe`** (ElevenLabs API; **`ELEVENLABS_API_KEY`**).
- **Alembic** — Migrations read **`DATABASE_URL`** or **`POSTGRES_HOST`**, **`POSTGRES_PORT`**, **`POSTGRES_DB`**, **`POSTGRES_USER`**, **`POSTGRES_PASSWORD`** (see [.env.example](reference/.env.example)).

For a minimal path from zero to a running station, follow [Quick Start](quick-start.md); for hardware and rig-specific details, see [Radio Usage](radio-usage.md).
