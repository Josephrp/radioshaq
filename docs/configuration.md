# Configuration

RadioShaq is configured via a single **Pydantic Settings** model (`radioshaq.config.schema.Config`). You can use **environment variables**, an optional **YAML/JSON file**, or both. Environment variables override file values, so you can keep secrets in env and the rest in a file. This page explains how configuration is loaded, how to go from zero to a running station, and documents every option.

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

## Setup to operate: the big picture

To **set up** and **operate** a RadioShaq station you typically:

1. **Install** — Clone the repo, install dependencies (e.g. `uv sync --extra dev --extra test` in `radioshaq/`), and ensure Python 3.11+, optional Docker for Postgres, optional Node for PM2.
2. **Database** — Run PostgreSQL (e.g. Docker on port 5434), set `RADIOSHAQ_DATABASE__POSTGRES_URL` (or use the default), run migrations (`alembic upgrade head` from `radioshaq/` or `python radioshaq/infrastructure/local/run_alembic.py upgrade head` from repo root).
3. **Auth** — Set `RADIOSHAQ_JWT__SECRET_KEY` to a secure value in production. Optionally adjust token expiry (`RADIOSHAQ_JWT__FIELD_TOKEN_EXPIRE_HOURS`, etc.).
4. **LLM** — Set provider and model (e.g. `RADIOSHAQ_LLM__PROVIDER=mistral`, `RADIOSHAQ_LLM__MODEL=mistral-large-latest`) and the corresponding API key (e.g. `RADIOSHAQ_LLM__MISTRAL_API_KEY` or your provider’s env name).
5. **Mode** — Set `RADIOSHAQ_MODE=field` (or `hq`, `receiver`) so the app knows whether it’s a field station, HQ, or receiver.
6. **Radio (optional)** — To attach a rig: set `RADIOSHAQ_RADIO__ENABLED=true`, `RADIOSHAQ_RADIO__RIG_MODEL` (Hamlib model ID), and `RADIOSHAQ_RADIO__PORT` (e.g. `COM3` or `/dev/ttyUSB0`). Optionally enable FLDIGI, packet, or SDR TX and set their options.
7. **Audio / voice (optional)** — For the voice_rx pipeline (listen or respond on air): set `RADIOSHAQ_RADIO__AUDIO_INPUT_ENABLED=true` and configure `audio.*` (input device, VAD, ASR, response_mode, trigger_phrases).
8. **Run** — Start the API (`uv run python -m radioshaq.api.server` from `radioshaq/`). Optionally enable the MessageBus consumer with `RADIOSHAQ_BUS_CONSUMER_ENABLED=1`.
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
--8<-- "docs/snippets/migrate-up.sh"
```

See [Quick Start](quick-start.md) and [Legacy](legacy/index.md) for credentials and troubleshooting.

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

The orchestrator and judge use an LLM for reasoning and evaluation. Set the provider, model, and the matching API key.

| Option | Env var | Default | Description |
|--------|---------|---------|-------------|
| `llm.provider` | `RADIOSHAQ_LLM__PROVIDER` | `mistral` | One of: `mistral`, `openai`, `anthropic`, `custom`. |
| `llm.model` | `RADIOSHAQ_LLM__MODEL` | `mistral-large-latest` | Model name (e.g. `mistral-small-latest`, `gpt-4o`). |
| `llm.mistral_api_key` | `RADIOSHAQ_LLM__MISTRAL_API_KEY` | `null` | Mistral API key (or set `MISTRAL_API_KEY` if your code reads it). |
| `llm.openai_api_key` | `RADIOSHAQ_LLM__OPENAI_API_KEY` | `null` | OpenAI API key. |
| `llm.anthropic_api_key` | `RADIOSHAQ_LLM__ANTHROPIC_API_KEY` | `null` | Anthropic API key. |
| `llm.custom_api_base` | `RADIOSHAQ_LLM__CUSTOM_API_BASE` | `null` | Custom provider base URL. |
| `llm.custom_api_key` | `RADIOSHAQ_LLM__CUSTOM_API_KEY` | `null` | Custom provider API key. |
| `llm.temperature` | `RADIOSHAQ_LLM__TEMPERATURE` | `0.1` | Sampling temperature (0–2). |
| `llm.max_tokens` | `RADIOSHAQ_LLM__MAX_TOKENS` | `4096` | Max tokens per response. |
| `llm.timeout_seconds` | `RADIOSHAQ_LLM__TIMEOUT_SECONDS` | `60.0` | Request timeout. |
| `llm.max_retries` | `RADIOSHAQ_LLM__MAX_RETRIES` | `3` | Retries on failure. |
| `llm.retry_delay_seconds` | `RADIOSHAQ_LLM__RETRY_DELAY_SECONDS` | `1.0` | Delay between retries. |

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
| `radio.tx_audit_log_path` | `RADIOSHAQ_RADIO__TX_AUDIT_LOG_PATH` | `null` | Path to JSONL file for TX audit log. |
| `radio.tx_allowed_bands_only` | `RADIOSHAQ_RADIO__TX_ALLOWED_BANDS_ONLY` | `true` | Restrict TX to band_plan bands. |
| `radio.restricted_bands_region` | `RADIOSHAQ_RADIO__RESTRICTED_BANDS_REGION` | `FCC` | Region for restricted bands: `FCC`, `CEPT`. |
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
| `audio.asr_model` | `RADIOSHAQ_AUDIO__ASR_MODEL` | `voxtral` | ASR model name. |
| `audio.asr_language` | `RADIOSHAQ_AUDIO__ASR_LANGUAGE` | `en` | ASR language. |
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

---

## Other runtime behavior

- **MessageBus consumer** — The API can run an inbound message consumer in the background so external systems can push work into the REACT loop. Set **`RADIOSHAQ_BUS_CONSUMER_ENABLED=1`** (or `true`/`yes`) to enable it. If not set, the consumer is disabled.
- **API host/port** — The server uses `API_HOST` / `API_PORT` or **`RADIOSHAQ_API_HOST`** / **`RADIOSHAQ_API_PORT`** when starting uvicorn (default from `hq.host` and `hq.port`).

For a minimal path from zero to a running station, follow [Quick Start](quick-start.md); for hardware and rig-specific details, see [Radio Usage](radio-usage.md).
