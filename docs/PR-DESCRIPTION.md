# PR: Dashboard, CLI, metrics, and radio status

## Summary

Adds a full dashboard and CLI for RadioShaq, Prometheus metrics and GPU gauges, live API/auth/radio status in the UI, and radio connection detection. Removes the interface/dashboard report and Legacy from the docs nav.

---

## Dashboard (web interface)

- **Layout & routing:** Single app with nav for Audio, Callsigns, Messages, Transcripts, Radio (React Router).
- **Live status bar (ApiStatus):**
  - **API:** Polls `GET /health` every 6s; shows ● live / ○ disconnected.
  - **Auth:** Polls `GET /auth/me` every 10s; in-app “Get token” (subject, role, station ID) and Logout.
  - **Radio:** Polls `GET /radio/status` every 8s when authenticated; shows ● connected (with freq/mode/PTT) or ○ not connected.
- **Polling:** Pending audio queue (5s in confirm mode), callsigns list (20s), transcripts (10s), bands (60s). Silent refresh where appropriate to avoid loading flicker.
- **VAD WebSocket:** Reconnect with backoff on disconnect; backend can push real metrics via `app.state.audio_metrics_latest`.
- **API client (`radioshaqApi.ts`):** Auth, health, audio, callsigns, messages (process, whitelist, inject, inject-and-store, relay), transcripts, radio (status, bands, send-tts). Optional runtime token via `setApiToken()`.
- **Pages:** Audio (response mode, activation, devices, VAD, confirmation queue), Callsigns (list, add, remove, register-from-audio), Messages (Process, Whitelist, Inject, Inject & store, Relay), Transcripts (search, play), Radio (bands, send TTS). Title “SHAKODS Audio” → “RadioShaq Audio.”

---

## CLI

- **`radioshaq` / `python -m radioshaq`** (Typer): full server coverage.
- **Commands:** `health` (optional `--ready`), `token` (subject, role, station-id), `callsigns` (list), `callsigns add <callsign>`, `callsigns remove <callsign>`, `message process "<text>"`, `message inject "..."`, `message relay`, `transcripts list` (filters), `transcripts play <id>`, `radio bands`, `radio send-tts "<msg>"`, `run-api` (uvicorn).
- **Env:** `RADIOSHAQ_API`, `RADIOSHAQ_TOKEN`. Shared helpers `_api_get`, `_api_post`, `_api_delete` for consistent auth and errors.

---

## Backend

- **`GET /metrics`:** Prometheus scrape. Gauges: `radioshaq_uptime_seconds`, `radioshaq_callsigns_registered_total`, optional GPU (`radioshaq_gpu_utilization_percent`, `radioshaq_gpu_memory_used_mb`, `radioshaq_gpu_memory_total_mb`) when `nvidia-smi` is available. Works without `prometheus-client` (fallback text); optional dep: `uv sync --extra metrics`.
- **`GET /radio/status`:** Returns `{ connected, reason?, frequency_hz?, mode?, ptt? }`. Uses `RigManager.is_connected()` and optional `get_state()` for freq/mode/PTT.
- **`RigManager.is_connected(rig_name=None)`:** Returns whether the active (or specified) CAT rig is connected.
- **WebSocket `/ws/audio/metrics/{session_id}`:** Sends `app.state.audio_metrics_latest` when set (for real VAD/SNR from voice_rx); otherwise placeholder heartbeat.

---

## Docs

- **New:** `docs/monitoring.md` — Prometheus `/metrics`, GPU, VAD WebSocket contract.
- **Updated:** `api-reference.md` (metrics and radio status), `radioshaq/README.md` (Monitoring section).
- **Removed from nav:** “Interface & dashboard report” and “Legacy”. Deleted `docs/legacy/index.md`.

---

## Optional dependency

- **`[metrics]`** in `pyproject.toml`: `prometheus-client>=0.21` for full Prometheus exposition (optional; fallback works without it).

---

## Testing

- Manual: dashboard with API on/off, get token, radio status; CLI commands against running API.
- Existing unit/integration tests unchanged.
