# API Reference

The RadioShaq API is a FastAPI application. All protected endpoints require a **Bearer JWT** from `POST /auth/token` (query params: `subject`, `role`, `station_id`).

**Interactive docs:** When the API is running, see **http://localhost:8000/docs** (Swagger UI) and **http://localhost:8000/redoc**.

## Overview

| Area | Prefix | Purpose |
|------|--------|---------|
| Health | `/health`, `/health/ready` | Liveness and readiness (DB, orchestrator) |
| Metrics | `/metrics` | Prometheus scrape (uptime, callsigns, optional GPU). See [Response & compliance](response-compliance-and-monitoring.md). |
| Auth | `/auth/token`, `/auth/refresh`, `/auth/me` | Issue token, refresh, current user |
| Messages | `/messages/process`, `/messages/whitelist-request`, `/messages/from-audio`, `/messages/inject-and-store` | Orchestration and whitelist flow |
| Relay | `/messages/relay` | Band translation (e.g. 40m → 2m). Stores source + relayed transcripts; optional inject/TX when config enables. Recipients **poll** `GET /transcripts?callsign=<callsign>&destination_only=true&band=<band>` to retrieve relayed messages. |
| Callsigns | `/callsigns`, `/callsigns/register`, `/callsigns/register-from-audio`, `/callsigns/registered/{callsign}` (GET, PATCH, DELETE), `/callsigns/registered/{callsign}/contact-preferences` (GET, PATCH) | Registered callsigns, registration, update/delete, and contact preferences (notify-on-relay, consent). |
| **Config** | `/api/v1/config/llm`, `/api/v1/config/memory`, `/api/v1/config/overrides` | LLM, memory (Hindsight), and per-role overrides (GET/PATCH; keys redacted). See [Configuration](configuration.md#per-role-and-per-subagent-overrides). |
| Audio | `/api/v1/config/audio`, `/api/v1/config/audio/reset`, `/api/v1/audio/devices`, `/api/v1/audio/devices/{device_id}/test`, `/api/v1/audio/pending`, approve/reject | Audio config, reset, device list, device test, and pending response queue |
| Transcripts | `/transcripts`, `/transcripts/{id}`, `/transcripts/{id}/play` | Search and play transcripts |
| Radio | `/radio/status`, `/radio/propagation`, `/radio/bands`, `/radio/send-tts`, `POST /radio/send-audio` | Radio connected?, propagation, band list, send TTS, upload audio file for TX |
| **GIS** | `/gis/location`, `/gis/location/{callsign}`, `/gis/operators-nearby`, `GET /gis/emergency-events` | Store/retrieve operator location (lat/lon), find operators within radius, emergency events with location for map overlays. |
| **Emergency** | `/emergency/request`, `/emergency/pending-count`, `/emergency/events`, `/emergency/events/stream`, `/emergency/events/{id}/approve`, `/emergency/events/{id}/reject` | Request emergency flow, pending count, list events, SSE stream, approve/reject event |
| **Memory** | `/memory/{callsign}/blocks` (GET, PUT, POST append), `/memory/{callsign}/summaries` (GET) | Per-callsign memory blocks and summaries |
| **Receiver** | `POST /receiver/upload` | Receiver service upload to HQ/field |
| Inject | `/inject/message` | Demo: push message into RX injection queue |
| Internal | `/internal/bus/inbound`, `POST /internal/opt-out` | MessageBus inbound (e.g. Lambda); SMS/WhatsApp opt-out |

### GIS location (PostGIS)

- **POST /gis/location** — Store operator location. Body: `callsign` (required), `latitude` and `longitude` (required for v1), optional `accuracy_meters`, `altitude_meters`. If only `location_text` is sent, returns 400 with `error: "ambiguous_location"`. Response: `id`, `callsign`, `latitude`, `longitude`, `source` (e.g. `user_disclosed`), `timestamp`, `confidence`. Coordinates `0.0, 0.0` are valid.
- **GET /gis/location/{callsign}** — Latest stored location for callsign (explicit lat/lon). 404 if none.
- **GET /gis/operators-nearby** — Query: `latitude`, `longitude`, `radius_meters` (default 50000), optional `recent_hours` (default 24), `max_results` (default 100). Returns list of operators with `distance_meters`.
- **GET /gis/emergency-events** — Emergency events with location for map overlays. Query: `since` (ISO datetime), `status`, `limit`. Returns events with location data.

Generated API reference from the FastAPI OpenAPI spec (run `python radioshaq/scripts/export_openapi.py` from repo root before building to produce `docs/api/openapi.json`):

[OpenAPI spec](api/openapi.json)
