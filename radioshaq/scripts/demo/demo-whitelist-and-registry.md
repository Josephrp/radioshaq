# Whitelist + callsign registry demo

This demo exercises **callsign registration** and the **WhitelistAgent**: register callsigns via the API, then submit a whitelist request (text or audio) that the orchestrator evaluates with the LLM and may register or respond.

## What you get

- **POST /callsigns/register**: Add callsigns to the allowlist so from-audio and relay accept them.
- **POST /messages/whitelist-request**: Submit a request (e.g. "I am requesting to be whitelisted for cross band relay"); orchestrator runs WhitelistAgent and may register the callsign or return a policy message.

## Prerequisites

- **HQ API** with orchestrator and **LLM** configured.
- **Postgres** (optional but recommended for DB-backed registry).
- **JWT** via POST /auth/token.

## Steps

### 1. Start HQ

```bash
cd radioshaq
uv run radioshaq run-api
```

### 2. Run the whitelist flow demo script

```bash
cd radioshaq
uv run python scripts/demo/run_whitelist_flow_demo.py \
  --base-url http://localhost:8000 \
  --callsigns FLABC-1 F1XYZ-1
```

- **Expected**: Register returns 200 for each callsign; whitelist-request returns 200 (or 503 if orchestrator unavailable).
- **Success criteria**: Script exits 0; no 4xx from register or whitelist-request.

### 3. Manual register + whitelist-request

```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=DEMO-01" | jq -r .access_token)
curl -s -X POST "http://localhost:8000/callsigns/register" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"callsign":"FLABC-1","source":"api"}'
curl -s -X POST "http://localhost:8000/messages/whitelist-request" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"I am requesting to be whitelisted for cross band relay. Over.","callsign":"FLABC-1"}'
```

## See also

- [coverage-matrix.md](coverage-matrix.md) — Whitelist + registry row.
- [option-c-recording-scripts.md](option-c-recording-scripts.md) — 01_whitelist_request.wav script.
