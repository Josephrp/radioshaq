# Voice RX audio demo (radio_rx_audio + ASR + triggers + confirmation)

This demo exercises the **voice monitoring path**: `RadioAudioReceptionAgent` (`radio_rx_audio`) with ASR, trigger phrases, optional audio activation phrase, and human-in-the-loop confirmation (LISTEN_ONLY, CONFIRM_FIRST, CONFIRM_TIMEOUT, AUTO_RESPOND).

## What you get

- **HQ** running with **voice listener** enabled: rig (or virtual) audio → capture → ASR → trigger filter → optional store + message bus publish → optional LLM response and TX.
- **Trigger filter**: optional callsign and trigger phrases; CONTAINS / EXACT / STARTS_WITH / FUZZY.
- **Confirmation manager**: pending responses visible at `GET /audio/pending`; approve/reject via API or auto-send on timeout when `response_mode=confirm_timeout`.
- **Transcript storage**: when `voice_store_transcript` is enabled, voice segments are stored for `GET /transcripts`.

## Prerequisites

- **HQ API** running with:
  - `radio.audio_input_enabled=true` and `radio.voice_listener_enabled=true` (or `audio_monitoring_enabled=true`).
  - ASR configured (e.g. ElevenLabs Scribe or local model).
  - Optional: LLM and TTS for auto/confirm response; message bus for publishing inbound.
- **Audio input**: real rig audio via sound device, or virtual cable / loopback playing a WAV so the voice pipeline receives speech.
- **Postgres** (optional but recommended for transcript storage).
- **JWT secret** and auth working (`POST /auth/token`).

## Steps

### 1. Configure HQ for voice listener

Environment or `config.yaml`:

```bash
export RADIOSHAQ_RADIO__AUDIO_INPUT_ENABLED=true
export RADIOSHAQ_RADIO__VOICE_LISTENER_ENABLED=true
export RADIOSHAQ_RADIO__DEFAULT_BAND=2m
# Optional: trigger and response mode
# export RADIOSHAQ_AUDIO__TRIGGER_ENABLED=true
# export RADIOSHAQ_AUDIO__TRIGGER_PHRASES="radioshaq,over"
# export RADIOSHAQ_AUDIO__RESPONSE_MODE=confirm_first
```

### 2. Start HQ

```bash
cd radioshaq
uv run radioshaq run-api
```

Ensure logs show: `Voice listener started for band 2m (...)`.

### 3. Run the voice RX audio demo script

The script polls `/health`, `/config/audio`, `/audio/pending`, and `/transcripts` to verify the voice path is active and to report activity after a short run.

```bash
cd radioshaq
uv run python scripts/demo/run_voice_rx_audio_demo.py \
  --base-url http://localhost:8000 \
  --duration 30
```

- **Expected**: Script reports audio config, pending count, and transcript count. If you speak (or play a WAV into the configured input) and triggers match, you should see pending responses or new transcripts.
- **Success criteria**: HQ started with voice listener; script exits 0 and prints a short summary (transcripts and/or pending counts). No HTTP 5xx from demo script.

### 4. Optional: approve a pending response

If `response_mode=confirm_first` or `confirm_timeout`:

```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=DEMO-01" | jq -r .access_token)
curl -s -X GET "http://localhost:8000/audio/pending" -H "Authorization: Bearer $TOKEN"
# Approve one (use pending_id from the list):
curl -s -X POST "http://localhost:8000/audio/pending/<pending_id>/approve" -H "Authorization: Bearer $TOKEN"
```

## Troubleshooting

- **Voice listener not started**: Check `audio_input_enabled` and `voice_listener_enabled`; ensure `radio_rx_audio` agent is registered (orchestrator + agent_registry).
- **No transcripts**: Confirm audio input device and level; check ASR model and `min_snr_db`; if using triggers, ensure phrase/callsign matches.
- **No pending responses**: Response mode must be `confirm_first` or `confirm_timeout`; trigger must have fired and response generated.

## See also

- [coverage-matrix.md](coverage-matrix.md) — Voice RX audio row.
- [demo-hackrf-full.md](demo-hackrf-full.md) — Full HackRF RX/TX and receiver uploads.
