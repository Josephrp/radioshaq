# Option C live demo (no Twilio)

This is the **full Option C** flow (from-audio, inject-and-store, relay, HackRF TX, transcripts) with **Twilio explicitly disabled** so you can run without SMS/WhatsApp credentials. For full live behaviour, use **real HackRF** (SDR TX) and a **real LLM** (Mistral, OpenAI, etc.); stub mode is for CI/tests only.

## What you get

- **Auth**, **health**, **bands**, **propagation** (if configured).
- **POST /messages/from-audio**: upload WAVs; ASR → transcript storage and optional inject.
- **POST /messages/inject-and-store**: text inject + store.
- **POST /messages/relay** (target_channel=radio): band translation; message stored for destination.
- **POST /radio/send-audio** and **POST /radio/send-tts**: HackRF SDR TX when enabled.
- **GET /transcripts**: list recent transcripts.
- **No Twilio**: SMS/WhatsApp relay steps are skipped when you pass `--no-twilio` (or omit `--sms-to` and `--whatsapp-to`).

## Prerequisites

- **HQ API** running (`uv run radioshaq run-api`).
- **Postgres** migrated (recommended for transcript storage).
- **LLM** (Mistral/OpenAI/etc.) for any orchestrator/whitelist flows you trigger.
- **ASR** (e.g. ElevenLabs) for from-audio.
- **TTS** (e.g. ElevenLabs) for send-tts.
- **HackRF** (required for TX steps): real hardware for send-audio/send-tts; set `radio.sdr_tx_enabled=true`, `radio.sdr_tx_backend=hackrf`, attach device, and `uv sync --extra hackrf`. Use `--require-hardware` to exit non-zero if SDR TX is not configured.
- **Callsigns**: Register source/dest callsigns (e.g. `FLABC-1`, `F1XYZ-1`) via `POST /callsigns/register` or `radio.allowed_callsigns`.

## Steps

### 1. Register demo callsigns (if registry required)

```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=DEMO-01" | jq -r .access_token)
curl -s -X POST "http://localhost:8000/callsigns/register" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"callsign":"FLABC-1","source":"api"}'
curl -s -X POST "http://localhost:8000/callsigns/register" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"callsign":"F1XYZ-1","source":"api"}'
```

### 2. Prepare recordings

Place WAV files in a folder (e.g. `scripts/demo/recordings/`). Suggested content: see [option-c-recording-scripts.md](option-c-recording-scripts.md).

### 3. Run Option C with no Twilio

```bash
cd radioshaq
uv run python scripts/demo/run_full_live_demo_option_c.py \
  --base-url http://localhost:8000 \
  --recordings-dir scripts/demo/recordings \
  --source-callsign FLABC-1 \
  --dest-callsign F1XYZ-1 \
  --band 40m \
  --tx-frequency-hz 145520000 \
  --tx-mode NFM \
  --no-twilio \
  --require-hardware
```

- **Expected**: Auth, health, bands, propagation (if available), from-audio uploads, inject-and-store, relay (radio), send-audio, send-tts, transcripts. No SMS/WhatsApp steps; script prints that Twilio is skipped.
- **Success criteria**: All HTTP calls return 2xx (except propagation if not configured); transcript count includes uploaded and injected entries; script exits 0.

### 4. Env summary (no Twilio)

- `RADIOSHAQ_JWT__SECRET_KEY` — same as any demo.
- `RADIOSHAQ_RADIO__SDR_TX_ENABLED=true`, `RADIOSHAQ_RADIO__SDR_TX_BACKEND=hackrf` — for HackRF TX.
- `RADIOSHAQ_BUS_CONSUMER_ENABLED=1` — for relay outbound handler (radio path only when Twilio not used).
- LLM and ASR/TTS keys as needed.
- **Do not set** Twilio vars if you only want this no-Twilio run.

## See also

- [demo-hackrf-full.md](demo-hackrf-full.md) — Full HackRF + receiver + Option C with Twilio.
- [coverage-matrix.md](coverage-matrix.md) — Option C no-Twilio row.
