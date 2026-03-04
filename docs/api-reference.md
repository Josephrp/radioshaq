# API Reference

The RadioShaq API is a FastAPI application. All protected endpoints require a **Bearer JWT** from `POST /auth/token` (query params: `subject`, `role`, `station_id`).

**Interactive docs:** When the API is running, see **http://localhost:8000/docs** (Swagger UI) and **http://localhost:8000/redoc**.

## Overview

| Area | Prefix | Purpose |
|------|--------|---------|
| Health | `/health`, `/health/ready` | Liveness and readiness (DB, orchestrator) |
| Metrics | `/metrics` | Prometheus scrape (uptime, callsigns, optional GPU). See [Monitoring](monitoring.md). |
| Auth | `/auth/token`, `/auth/refresh`, `/auth/me` | Issue token, refresh, current user |
| Messages | `/messages/process`, `/messages/whitelist-request`, `/messages/from-audio`, `/messages/inject-and-store` | Orchestration and whitelist flow |
| Relay | `/messages/relay` | Band translation (e.g. 40m → 2m). Stores source + relayed transcripts; optional inject/TX when config enables. Recipients **poll** `GET /transcripts?callsign=<callsign>&destination_only=true&band=<band>` to retrieve relayed messages. |
| Callsigns | `/callsigns`, `/callsigns/register`, `/callsigns/register-from-audio`, `/callsigns/registered/{callsign}` | Registered callsigns and registration |
| **Config** | `/api/v1/config/llm`, `/api/v1/config/memory`, `/api/v1/config/overrides` | LLM, memory (Hindsight), and per-role overrides (GET/PATCH; keys redacted). See [Configuration](configuration.md#per-role-and-per-subagent-overrides). |
| Audio | `/api/v1/config/audio`, `/api/v1/audio/devices`, `/api/v1/audio/pending`, approve/reject | Audio config and pending response queue |
| Transcripts | `/transcripts`, `/transcripts/{id}`, `/transcripts/{id}/play` | Search and play transcripts |
| Radio | `/radio/status`, `/radio/propagation`, `/radio/bands`, `/radio/send-tts` | Radio connected?, propagation, band list, send TTS |
| Inject | `/inject/message` | Demo: push message into RX injection queue |
| Internal | `/internal/bus/inbound` | MessageBus inbound (e.g. Lambda) |

Generated API reference from the FastAPI OpenAPI spec (run `python radioshaq/scripts/export_openapi.py` from repo root before building to produce `docs/api/openapi.json`):

[OAD(docs/api/openapi.json)]
