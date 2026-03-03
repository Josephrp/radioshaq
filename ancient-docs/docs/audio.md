# SHAKODS Audio Pipeline

This document describes the audio capture → ASR → agent → TTS → TX pipeline and operator workflows.

## Overview

- **Audio capture**: Rig line-out → `AudioCaptureService` + `AudioStreamProcessor` (VAD, denoising).
- **ASR**: Voxtral (or Whisper fallback) transcribes speech segments.
- **Agent**: `RadioAudioReceptionAgent` applies trigger filtering and response mode logic.
- **Response modes**: Listen only, Confirm first (human approval), Confirm timeout, Auto-respond.
- **TX**: `RadioTransmissionAgent` with optional `PTTCoordinator` for half-duplex safety.

## PTT Coordinator (safety)

When `config.audio.ptt_coordination_enabled` is true (default), voice transmissions go through `PTTCoordinator`:

1. **Request transmit** – Checks that we are not already TX and that the channel is not busy (PTT not active).
2. **Begin transmit** – Keys PTT after a final check.
3. **End transmit** – Releases PTT and enters a short cooldown before allowing RX again.
4. **Break-in** – Operator can abort an automated transmission (e.g. manual PTT) when `break_in_enabled` is true.

This prevents keying over another station and respects half-duplex discipline.

## Confirmation queue (human-in-the-loop)

When **response mode** is **Confirm first** or **Confirm timeout**:

1. Incoming speech is transcribed and, if it passes the trigger filter, a proposed reply is generated.
2. The reply is added to the **pending responses** queue instead of being sent immediately.
3. An operator can:
   - **Approve** – The reply is sent over the radio (via the TX agent).
   - **Reject** – The reply is discarded (optional notes).

**API**

- `GET /api/v1/audio/pending` – List pending responses (requires auth).
- `POST /api/v1/audio/pending/{id}/approve` – Approve and send (body: `{ "operator": "optional-id" }`).
- `POST /api/v1/audio/pending/{id}/reject` – Reject (body: `{ "operator", "notes" }`).

**Web UI**

The React app in `web-interface/` provides a confirmation queue view and approve/reject buttons when response mode is confirm_first or confirm_timeout.

## Audio API (config and devices)

- `GET /api/v1/config/audio` – Current audio configuration.
- `PATCH /api/v1/config/audio` – Update config (runtime overlay; does not persist to file).
- `POST /api/v1/config/audio/reset` – Clear runtime overrides.
- `GET /api/v1/audio/devices` – List input/output audio devices (requires `voice_rx` deps).
- `POST /api/v1/audio/devices/{id}/test` – Test device by index.
- `WebSocket /ws/audio/metrics/{session_id}` – Placeholder for real-time VAD/metrics.

## Health check

`GET /health/ready` includes an `audio_agent` check when the agent registry is available: `"registered"` if `radio_rx_audio` is registered, otherwise `"not_registered"`.

## Enabling the audio pipeline

1. Install optional deps: `uv sync --extra audio --extra voice_tx --extra voice_rx`
2. Set `SHAKODS_RADIO__AUDIO_INPUT_ENABLED=1` (or in `config.yaml`: `radio.audio_input_enabled: true`).
3. Configure `audio` section (see `examples/config_sample.yaml`).
4. Use the web interface or API to set response mode and manage the confirmation queue.
