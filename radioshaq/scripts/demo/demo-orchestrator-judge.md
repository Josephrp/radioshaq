# Orchestrator + Judge demo (REACT loop and agent routing)

This demo exercises the **orchestrator** and **Judge**: inbound messages are processed by the REACT loop, which decomposes tasks and routes them to specialized agents (radio_tx, whitelist, sms, gis, scheduler, etc.) via the agent registry and Judge.

## What you get

- **POST /messages/process**: Submit a message; orchestrator runs REACT (think → act → observe) and returns a final reply.
- **Agent routing**: Judge and registry select agents by capability or explicit name (e.g. `radio_tx`, `scheduler`, `gis`).
- **Message bus path**: When the bus consumer is enabled, messages published to the bus (e.g. from inject or voice_rx_audio) are also processed by the same orchestrator.

## Prerequisites

- **HQ API** with orchestrator and LLM configured (Mistral, OpenAI, etc.).
- **Message bus** optional; for process API only, bus is not required.
- **JWT** via POST /auth/token.

## Steps

### 1. Start HQ

```bash
cd radioshaq
uv run radioshaq run-api
```

Ensure logs show orchestrator and agent registry (no "Orchestrator not created").

### 2. Run the orchestrator/judge demo script

The script sends several messages via POST /messages/process that are designed to trigger different agent paths (e.g. scheduling, propagation, simple reply).

```bash
cd radioshaq
uv run python scripts/demo/run_orchestrator_judge_demo.py \
  --base-url http://localhost:8000
```

- **Expected**: Each request returns HTTP 200; response includes `success` and `message` (orchestrator reply).
- **Success criteria**: All process calls return 200; script exits 0. Agent selection is internal; you can inspect HQ logs to see which agents were invoked.

### 3. Manual process example

```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=DEMO-01" | jq -r .access_token)
curl -s -X POST "http://localhost:8000/messages/process" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"message":"What is the propagation from San Francisco to Los Angeles?"}'
```

## See also

- [coverage-matrix.md](coverage-matrix.md) — Orchestrator + Judge row.
- [demo-whitelist-and-registry.md](demo-whitelist-and-registry.md) — Whitelist agent via whitelist-request.
