# RadioShaq Interface, Dashboard & Client Report

**Date:** 2026-03-03  
**Scope:** Web interface, API implementation, monitoring (Prometheus/GPU), dashboard commands/triggers, and modular client design (web + CLI).

---

## 1. How the Interface Works

### 1.1 Architecture Overview

- **Backend:** FastAPI app (`radioshaq.api.server`) with lifespan-managed resources: config, PostGIS DB, callsign repository, MessageBus, orchestrator, tool registry, optional bus consumer.
- **Frontend:** React + TypeScript SPA in `web-interface/`, built with Vite. Single page: **Audio Config** (response mode, devices, VAD/metrics, confirmation queue).
- **Auth:** JWT via `POST /auth/token` (subject, role, station_id). All protected routes require `Authorization: Bearer <token>`. Env: `VITE_RADIOSHAQ_TOKEN` for the UI.
- **Proxy:** Dev server (port 3000) proxies `/api` and `/ws` to the API (default port 8000). Env: `VITE_RADIOSHAQ_API` for API base URL.

### 1.2 Web UI Implementation (Current State)

| Component | Purpose | API / Protocol |
|-----------|---------|----------------|
| **ResponseModeSelector** | Switch among listen_only, confirm_first, confirm_timeout, auto_respond | `GET/PATCH /api/v1/config/audio` |
| **ConfirmationQueue** | List pending responses; approve or reject | `GET /api/v1/audio/pending`, `POST …/approve`, `POST …/reject` |
| **VADVisualizer** | Real-time VAD/SNR/state | WebSocket `ws://…/ws/audio/metrics/{sessionId}` |
| **Audio devices** | Show input/output device counts | `GET /api/v1/audio/devices` |

- **radioshaqApi.ts** is the only API client: no routing, no callsign/whitelist, no messages, no transcripts, no inject/relay. README still says "SHAKODS" in places; env vars use `VITE_RADIOSHAQ_*`.
- **VAD/metrics WebSocket** is a **placeholder**: server sends a fixed heartbeat every 1s (`vad_active: false`, `snr_db: null`, `state: "idle"`). No real pipeline wiring yet.

### 1.3 API Surface (Backend)

| Prefix | Router | Purpose |
|--------|--------|---------|
| `/health`, `/health/ready` | health | Liveness / readiness (DB, orchestrator, audio_agent) |
| `/auth/token`, `/auth/refresh`, `/auth/me` | auth | Issue token, refresh, current user |
| `/api/v1/config/audio`, `/api/v1/config/audio/reset` | audio | Get/patch/reset audio config (runtime overlay) |
| `/api/v1/audio/devices`, `/api/v1/audio/devices/{id}/test` | audio | List/test audio devices |
| `/api/v1/audio/pending`, `…/approve`, `…/reject` | audio | Pending response queue (requires audio agent) |
| `/ws/audio/metrics/{session_id}` | audio (ws) | Placeholder metrics WebSocket |
| `/callsigns` | callsigns | **List** registered; **POST /register**, **POST /register-from-audio**, **DELETE /registered/{callsign}** |
| `/messages/process` | messages | REACT orchestration (text/message) |
| `/messages/whitelist-request` | messages | Whitelist flow (text or audio → orchestrator → optional TTS reply) |
| `/messages/from-audio` | messages | Upload audio → ASR, whitelist check, store transcript, optional inject |
| `/messages/inject-and-store` | messages | Inject + store (whitelist enforced) |
| `/messages/relay` | relay | Band translation (e.g. 40m → 2m), store both sides |
| `/inject/message` | inject | Demo: push message into RX injection queue |
| `/transcripts` | transcripts | Search (callsign, band, freq, mode, since); GET by id; POST …/play (TTS over radio) |
| `/radio/propagation`, `/radio/bands`, `/radio/send-tts` | radio | Propagation, band list, send TTS |
| `/internal/bus/inbound` | bus | Publish InboundMessage to MessageBus (e.g. Lambda → consumer) |

OpenAPI docs: **http://localhost:8000/docs** (Swagger UI).

---

## 2. Monitoring: Current State and Gaps

### 2.1 What Exists Today

- **Health:** `/health` (liveness), `/health/ready` (DB, orchestrator, audio_agent). No metrics format.
- **VAD/metrics:** WebSocket placeholder only; no real VAD/SNR from the voice_rx pipeline.
- **Config:** `AudioConfig` (and full `Config`) hold many tunables (VAD, ASR, response_mode, etc.) but no instrumentation.
- **ASR:** `radioshaq.audio.asr` uses `device_map="auto"` (GPU if available); no GPU or latency metrics exposed.
- **PM2:** `ecosystem.config.js` runs API, bridge, orchestrator, radio, field-sync, with log paths and `max_memory_restart`; no custom metrics or Prometheus.

### 2.2 Useful Dashboard Metrics to Add (Recommendations)

**Prometheus-style metrics (suggested):**

- **HTTP:** Request count, latency histogram, status codes by path (e.g. `/api/v1/*`, `/callsigns/*`, `/messages/*`).
- **Orchestrator:** Requests in flight, completed/failed counts, iteration count per run, judge scores (if exposed).
- **Audio pipeline:** VAD events (start/stop), ASR invocations, latency, confidence; pending queue length; approve/reject/timeout counts.
- **Callsign/whitelist:** List size, register/unregister counts.
- **MessageBus:** Inbound queue length, publish/drop counts, consumer lag.
- **DB:** Connection pool usage, query latency (if using SQLAlchemy instrumentation).
- **GPU (when ASR/TTS use it):** Utilization %, memory allocated/used (e.g. via `nvidia_smi` or `pynvml`), per-process if possible. Optional: CUDA device index and name.

**Concrete implementation options:**

- Add **Prometheus client** (`prometheus_client`) and a `/metrics` endpoint; instrument key routes and the orchestrator/audio agent.
- Optionally a **small sidecar or background task** that samples GPU (e.g. `nvidia-smi --query-gpu=...`) and exposes as gauge metrics.
- **WebSocket metrics:** When the voice_rx pipeline runs, push real VAD/SNR/state on the existing `/ws/audio/metrics/{session_id}` so the dashboard shows live data.

### 2.3 GPU Usage (Current and Desired)

- **Current:** ASR (`voxtral`) uses `device_map="auto"` (GPU if CUDA available). No API or dashboard exposes GPU state.
- **Desired for dashboard:** At least one of: (1) Prometheus metrics for GPU utilization and memory, or (2) a simple `/system/gpu` (or `/health/gpu`) JSON endpoint for the UI to poll. Prefer metrics for consistency with Prometheus and alerting.

---

## 3. Dashboard Commands and Triggers (Useful to Expose)

These are **operations the dashboard (or any client) should be able to perform**; most are already in the API and only need to be wired in the UI or a shared client.

### 3.1 Callsign / Whitelist (High Value)

- **List whitelisted callsigns:** `GET /callsigns` → `{ registered, count }`.
- **Add callsign:** `POST /callsigns/register` body `{ callsign, source?: "api"|"audio" }` → `{ ok, callsign, id }`.
- **Remove callsign:** `DELETE /callsigns/registered/{callsign}`.
- **Register from audio:** `POST /callsigns/register-from-audio` (multipart file + optional `?callsign=XXX`). Useful for “approve this audio as callsign X”.

**Dashboard idea:** “Callsigns” panel: table of registered callsigns, “Add callsign” form, “Remove” per row; optional “Upload audio to register” flow.

### 3.2 Message and Orchestration Triggers

- **Process text (REACT):** `POST /messages/process` body `{ message or text, channel?, chat_id?, sender_id? }`. Good for “Send this to the orchestrator” from the dashboard.
- **Whitelist request (voice/text):** `POST /messages/whitelist-request` (JSON or multipart with file). Triggers whitelist flow and optional TTS reply.
- **Inject message (demo):** `POST /inject/message` body `{ text, band?, frequency_hz?, mode?, source_callsign?, destination_callsign?, ... }`. Simulate received message.
- **Inject and store:** `POST /messages/inject-and-store` (whitelist enforced). Combines inject + DB store.

**Dashboard idea:** “Commands” or “Triggers” panel: “Process message”, “Whitelist request”, “Inject message” with minimal forms (text, optional band/callsigns).

### 3.3 Radio and Playback

- **Send TTS:** `POST /radio/send-tts` body `{ message, frequency_hz?, mode? }`. Direct “say this on the radio.”
- **Relay:** `POST /messages/relay` body `{ message, source_band, target_band, source_callsign?, destination_callsign?, ... }`. Band translation.
- **Play transcript:** `POST /transcripts/{id}/play`. TTS + send over radio.

**Dashboard idea:** “Radio” panel: send TTS, relay form (source/target band, message), and “Recent transcripts” with “Play” per row.

### 3.4 Transcripts and History

- **Search:** `GET /transcripts?callsign=&band=&frequency_min=&frequency_max=&mode=&since=&limit=`.
- **Get one:** `GET /transcripts/{id}`.
- **Play:** `POST /transcripts/{id}/play` (above).

**Dashboard idea:** “Transcripts” panel: filters (callsign, band, since), table of results, “Play” action.

### 3.5 Auth (for Any Client)

- **Get token:** `POST /auth/token?subject=&role=&station_id=` → `{ access_token, token_type }`.
- **Current user:** `GET /auth/me` (Bearer) → `{ sub, role, station_id, scopes }`.

All dashboard and CLI flows need a token (or env token) for protected endpoints.

---

## 4. State of the Interface (Summary)

| Area | State | Notes |
|------|--------|-------|
| **Web UI** | Single page (Audio Config) | No callsigns, messages, transcripts, inject, or radio controls. README/env mix of SHAKODS/RadioShaq. |
| **API** | Rich and coherent | Health, auth, audio, callsigns, messages, relay, inject, transcripts, radio, internal bus. Well-suited for a dashboard. |
| **Auth** | JWT in place | Token creation and Bearer validation; UI can use `VITE_RADIOSHAQ_TOKEN`. |
| **Metrics** | Minimal | Only readiness and placeholder VAD WebSocket. No Prometheus, no GPU. |
| **CLI** | Declared but missing | `radioshaq` entry point points to `radioshaq.cli:app` but **no `radioshaq/cli.py`** in the repo; `python -m radioshaq` will fail until CLI is implemented or entry point fixed. |

---

## 5. Building a Modular, Maintainable Client

Goal: one coherent client layer that can drive both the **web dashboard** and **CLI** (or scripts), with minimal duplication and clear separation of concerns.

### 5.1 Shared Client Layer (Recommendation)

Introduce a **small client SDK** that both the React app and the CLI can use:

- **Option A – TypeScript/JavaScript:**  
  - Extend `web-interface/src/services/radioshaqApi.ts` into a full **API client module** (auth, audio, callsigns, messages, inject, relay, transcripts, radio, health).  
  - Export typed functions and, if desired, a single `RadioshaqClient` class with `baseUrl` and `getToken()`.  
  - Use from React (dashboard) and from Node scripts or a small CLI (e.g. `npx ts-node` or a bundled CLI).

- **Option B – Python:**  
  - Add `radioshaq.client` (or `radioshaq.api_client`) with async/sync wrappers around the same endpoints (using `httpx`).  
  - Use from the **Python CLI** (`radioshaq` command) and from scripts/tests.  
  - Dashboard stays on the existing TS API module but can mirror the same endpoint list.

- **Option C – Both:**  
  - TS client for the dashboard and Node-based tooling; Python client for `radioshaq` CLI and automation.  
  - Keep a **single source of truth** for “what the API offers”: e.g. OpenAPI spec generated from FastAPI, then generate or hand-maintain both clients so they stay in sync.

Recommendation: **Option C** with a **contract-first** approach: maintain OpenAPI (FastAPI already exposes it), then implement one small **Python client** for CLI/scripts and expand the **existing TS client** for the dashboard so both align to the same routes and payloads.

### 5.2 Modular Dashboard Structure

- **Routes/pages:** e.g. `/` (Audio), `/callsigns`, `/messages` (process + whitelist + inject), `/transcripts`, `/radio`, `/system` (health + future metrics/GPU). Use React Router or similar.
- **Feature-based modules:** e.g. `features/audio`, `features/callsigns`, `features/messages`, `features/transcripts`, `features/radio`, `features/system`. Each owns its API calls (via the shared client), types, and UI.
- **Shared:** One `radioshaqApi` (or `RadioshaqClient`) instance with base URL and token (from env or login flow); shared types for responses and request bodies.

This keeps the dashboard maintainable and makes it easy to add “Callsigns” and “Commands/Triggers” panels that call the endpoints listed in §3.

### 5.3 CLI Design (When Implemented)

- **Entry point:** Implement `radioshaq/cli.py` with Typer (or similar) so `radioshaq` and `python -m radioshaq` work.
- **Commands (suggested):**  
  - `radioshaq auth token` – get token (subject, role, station_id).  
  - `radioshaq health` – GET /health and /health/ready.  
  - `radioshaq callsigns list | add <callsign> | remove <callsign>`.  
  - `radioshaq message process "<text>"` | `whitelist-request ...` | `inject "..." --band 40m`.  
  - `radioshaq transcripts list [--callsign] [--band] [--since]` | `play <id>`.  
  - `radioshaq radio send-tts "<message>"` | `relay --source-band 40m --target-band 2m "..."`.  
- **Config:** Base URL and token from env (`RADIOSHAQ_API`, `RADIOSHAQ_TOKEN`) or flags; optionally reuse `Config` for defaults.
- **Implementation:** Use the Python API client (httpx) so all logic (URLs, payloads, errors) lives in one place; CLI only parses args and prints results.

### 5.4 Consistency Between Dashboard and CLI

- **Same endpoints:** Dashboard and CLI should call the same API (no “dashboard-only” or “CLI-only” backend routes).
- **Same auth:** Bearer token from env or from `POST /auth/token`; dashboard can have a “Login” that gets a token and stores it (e.g. in memory or localStorage) and the CLI can use `RADIOSHAQ_TOKEN` or `radioshaq auth token` output.
- **Same semantics:** e.g. “Add callsign” = `POST /callsigns/register` in both UI and CLI.

---

## 6. Recommended Next Steps (Prioritized)

1. **Fix or implement CLI:** Add `radioshaq/cli.py` (Typer) implementing at least `auth token`, `health`, and optionally `callsigns list/add/remove` so the declared entry point works.
2. **Extend web API client:** In `radioshaqApi.ts`, add: auth (token), callsigns (list, register, unregister, register-from-audio), messages (process, whitelist-request, inject-and-store), inject (message), transcripts (search, get, play), radio (bands, send-tts), relay (or document under messages). Add a minimal “get token” helper if the UI ever needs to obtain a token without env.
3. **Add dashboard panels:** Callsigns (list + add/remove), Commands (process, whitelist-request, inject), Transcripts (search + play), Radio (send-tts, relay). Reuse the expanded API client.
4. **Metrics and monitoring:** Add `/metrics` (Prometheus) with HTTP and core app metrics; optionally GPU gauges (e.g. from nvidia-smi or pynvml). Document in README.
5. **Real VAD/metrics:** When voice_rx pipeline is wired, push real VAD/SNR/state on the existing WebSocket so the dashboard shows live pipeline status.
6. **Naming and docs:** Replace remaining “SHAKODS” with “RadioShaq” in README and UI copy; standardize on `VITE_RADIOSHAQ_*` and `RADIOSHAQ_*` for env.

---

## 7. Quick Reference: API Endpoints for Clients

| Action | Method | Path | Body / Params |
|--------|--------|------|----------------|
| Liveness | GET | /health | - |
| Readiness | GET | /health/ready | - |
| Token | POST | /auth/token | subject, role?, station_id? |
| Me | GET | /auth/me | Bearer |
| Audio config | GET/PATCH | /api/v1/config/audio | PATCH: partial config |
| Audio devices | GET | /api/v1/audio/devices | - |
| Pending list | GET | /api/v1/audio/pending | - |
| Approve/Reject | POST | /api/v1/audio/pending/{id}/approve, .../reject | optional operator, notes |
| List callsigns | GET | /callsigns | - |
| Register callsign | POST | /callsigns/register | callsign, source? |
| Register from audio | POST | /callsigns/register-from-audio | multipart file, ?callsign= |
| Unregister | DELETE | /callsigns/registered/{callsign} | - |
| Process message | POST | /messages/process | message or text, channel?, chat_id?, sender_id? |
| Whitelist request | POST | /messages/whitelist-request | JSON or multipart (text/message, callsign?, file?) |
| Inject and store | POST | /messages/inject-and-store | text, band?, frequency_hz?, mode?, source_callsign?, destination_callsign?, ... |
| Relay | POST | /messages/relay | message, source_band, target_band, source_callsign?, destination_callsign?, ... |
| Inject (demo) | POST | /inject/message | text, band?, frequency_hz?, mode?, source_callsign?, destination_callsign?, ... |
| Search transcripts | GET | /transcripts | callsign?, band?, frequency_min?, frequency_max?, mode?, since?, limit? |
| Get transcript | GET | /transcripts/{id} | - |
| Play transcript | POST | /transcripts/{id}/play | - |
| Propagation | GET | /radio/propagation | lat_origin, lon_origin, lat_dest, lon_dest |
| Bands | GET | /radio/bands | - |
| Send TTS | POST | /radio/send-tts | message, frequency_hz?, mode? |
| Metrics WS | WS | /ws/audio/metrics/{session_id} | - |

All except `/health` and `/auth/token` (and optionally `/health/ready`) require `Authorization: Bearer <access_token>`.
