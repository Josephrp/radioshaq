# Demo environment profiles

Summary of **environment variables** for running the Live HackRF + LLM demo suite. For full WSL/HackRF setup and Option C env, see [scripts/demo/demo-hackrf-full.md](../scripts/demo/demo-hackrf-full.md).

**Live demos use real hardware and real LLM:** HackRF RX/TX and LLM providers are not stubbed in the documented demo flows. Set the env below and attach a HackRF; use `--require-hardware` in the relevant demo scripts to fail fast if SDR TX is not configured.

## Agent and API hooks (how demos drive the system)

- **radio_tx (RadioTransmissionAgent):** Invoked via `POST /radio/send-audio` (multipart WAV) and `POST /radio/send-tts` (JSON body with `message`, optional `frequency_hz`, `mode`). Requires `radio.sdr_tx_enabled=true` and `radio.sdr_tx_backend=hackrf` for HackRF; when not set or no hardware, the TX agent may still run and return success/false (e.g. "Rig manager not configured"). Compliance checks run before TX.
- **radio_rx_audio (RadioAudioReceptionAgent):** No one-off "start monitor" HTTP endpoint. The **voice listener** (server lifespan) starts the agent when `radio.audio_input_enabled` and `radio.voice_listener_enabled` (or `audio_monitoring_enabled`) are true. Demos that need voice RX either run HQ with that config and poll `GET /api/v1/audio/pending` and `GET /transcripts`, or use `POST /messages/from-audio` to simulate inbound voice.
- **radio_rx (RadioReceptionAgent):** Used by the band listener (injection queue consumer) or by tasks submitted via the orchestrator. Demos inject via `POST /inject/message` or `POST /messages/inject-and-store`; the band listener (when enabled) or a process-driven task consumes from the queue.
- **Orchestrator / Judge:** `POST /messages/process` (body: `message` or `text`, optional `channel`, `chat_id`, `sender_id`) runs the REACT loop and routes to agents. Used by run_orchestrator_judge_demo and run_scheduler_demo.
- **WhitelistAgent:** Invoked via `POST /messages/whitelist-request` (JSON or multipart with audio). Orchestrator evaluates and may call the whitelist agent; result in response or completed_tasks.
- **SchedulerAgent:** No direct HTTP endpoint; reached when the orchestrator selects it for a scheduling request (e.g. "Schedule a call for X with Y at Z"). Requires DB with coordination_events for persistence.

## HQ process (`uv run radioshaq run-api`)

- **Mode + JWT:** `RADIOSHAQ_MODE=hq`, `RADIOSHAQ_JWT__SECRET_KEY` (must match receiver `JWT_SECRET`).
- **Receiver uploads:** `RADIOSHAQ_RADIO__RECEIVER_UPLOAD_STORE=true`, `RADIOSHAQ_RADIO__RECEIVER_UPLOAD_INJECT=true`.
- **HackRF SDR TX:** `RADIOSHAQ_RADIO__SDR_TX_ENABLED=true`, `RADIOSHAQ_RADIO__SDR_TX_BACKEND=hackrf`.
- **Message bus consumer:** `RADIOSHAQ_BUS_CONSUMER_ENABLED=1`.
- **LLM:** e.g. `RADIOSHAQ_LLM__PROVIDER=mistral`, `MISTRAL_API_KEY` / `RADIOSHAQ_LLM__MISTRAL_API_KEY`.
- **ASR/TTS:** e.g. `ELEVENLABS_API_KEY`, `RADIOSHAQ_TTS__PROVIDER=elevenlabs`.
- **Voice listener (for voice_rx_audio demos):** `RADIOSHAQ_RADIO__AUDIO_INPUT_ENABLED=true`, `RADIOSHAQ_RADIO__VOICE_LISTENER_ENABLED=true`, `RADIOSHAQ_RADIO__DEFAULT_BAND=2m`.
- **Twilio:** Omit or leave unset for no-Twilio demos; set for Option C with SMS/WhatsApp.

## Remote receiver process (`uv run radioshaq run-receiver`)

- **JWT:** `JWT_SECRET` = same as HQ `RADIOSHAQ_JWT__SECRET_KEY`.
- **Identity:** `STATION_ID=HACKRF-DEMO`.
- **HackRF:** `SDR_TYPE=hackrf`, `HACKRF_INDEX=0`.
- **HQ upload:** `HQ_URL=http://localhost:8000`, `HQ_TOKEN=<from POST /auth/token>`.
- **Demod:** `RECEIVER_MODE=nfm`, `RECEIVER_AUDIO_RATE=48000`.

## Demo scripts

- **Base URL:** Pass `--base-url http://localhost:8000` (or remote). Scripts obtain a JWT via `POST /auth/token` (subject/role/station_id).
- **Extras:** `uv sync --extra hackrf` (receiver + stream), `uv sync --extra voice_tx` (HackRF TX from HQ), `uv sync --extra audio` (ASR) as needed.

## Database

- **Postgres:** `RADIOSHAQ_DATABASE__POSTGRES_URL` or default (e.g. Docker on 5434). Run `uv run radioshaq launch docker` then `cd radioshaq && uv run alembic upgrade head` before demos that use transcripts or registry.
