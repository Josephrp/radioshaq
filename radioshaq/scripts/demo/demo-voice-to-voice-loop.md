# Voice-to-voice loop demo (RX → ASR → LLM → TTS → TX)

This demo exercises an **end-to-end voice loop**: inbound voice (from WAV upload or voice listener) → ASR → optional LLM decision → TTS → radio TX. It ties together `radio_rx_audio` (or from-audio), orchestrator/response agent, and `radio_tx` with TTS. For live runs use **real HackRF** (SDR TX) and **real LLM/ASR/TTS**; use `--require-hardware` to ensure SDR TX is configured.

## What you get

- **From-audio** or **voice listener** as input.
- **ASR** → transcript; **LLM** (via response agent or orchestrator) produces reply text.
- **TTS** → audio; **radio_tx** (SDR or CAT) sends on the configured frequency/mode.
- One complete cycle: “inbound message” → “outbound spoken response on air”.

## Prerequisites

- **HQ API** with orchestrator, message bus, ASR, TTS, and radio TX (SDR or rig) configured.
- **HackRF** (real hardware) for TX when using SDR; `radio.sdr_tx_enabled=true`, device attached, `uv sync --extra hackrf`.
- **Callsigns** registered or allowed.
- **JWT** via `POST /auth/token`.

## Steps

### 1. Start HQ with voice listener (optional) or use from-audio only

For **from-audio only** you don’t need voice listener; the script can upload a WAV and then trigger relay/TX via API. For **live voice**, set `radio.audio_input_enabled=true` and `radio.voice_listener_enabled=true`.

### 2. Run the voice-to-voice loop demo script

The script can either:
- **A)** Upload a single WAV via `POST /messages/from-audio` (inject=true), then call `POST /messages/relay` or a process endpoint to trigger a reply, then call `POST /radio/send-tts` with the reply text; or  
- **B)** Rely on the voice listener already running and only drive `POST /radio/send-tts` with a fixed message to demonstrate the TX side of the loop.

Example (TX side only; reply message fixed):

```bash
cd radioshaq
uv run python scripts/demo/run_voice_to_voice_loop_demo.py \
  --base-url http://localhost:8000 \
  --wav scripts/demo/recordings/00_callsign_identity.wav \
  --reply-message "Acknowledged. Standing by." \
  --tx-frequency-hz 145520000 \
  --tx-mode NFM
```

- **Expected**: From-audio upload succeeds and injects; script calls send-tts with the reply message; TX response is 200 with `success: true`.
- **Success criteria**: Transcript created from WAV; send-tts returns 200 and success; script exits 0.

### 3. Full loop (manual)

1. Upload WAV: `POST /messages/from-audio` (inject=true).
2. Process or relay: `POST /messages/process` or `POST /messages/relay` so the orchestrator generates a reply.
3. Send reply on air: `POST /radio/send-tts` with the reply text (or use the tool from orchestrator that calls radio_tx).

## See also

- [demo-voice-rx-audio.md](demo-voice-rx-audio.md) — Voice RX path.
- [demo-hackrf-tx-audio.md](demo-hackrf-tx-audio.md) — TX path only.
- [coverage-matrix.md](coverage-matrix.md) — Voice-to-voice row.
