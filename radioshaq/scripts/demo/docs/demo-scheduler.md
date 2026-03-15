# Scheduler demo (SchedulerAgent + coordination events)

This demo exercises the **SchedulerAgent**: scheduling a call (or similar task) via the orchestrator, which delegates to the scheduler and persists a coordination event when the DB is configured.

## What you get

- **Orchestrator** receives a natural-language request to schedule a contact.
- **SchedulerAgent** is selected (by capability or Judge) and runs `schedule_call`; when DB is available, it calls `store_coordination_event`.
- **Coordination events** are stored in the `coordination_events` table (Postgres/PostGIS) for later use by relay delivery or other workers.

## Prerequisites

- **HQ API** with orchestrator, LLM, and **Postgres** (with coordination_events table migrated).
- **JWT** via POST /auth/token.

## Steps

### 1. Start HQ and ensure DB is migrated

```bash
cd radioshaq
uv run alembic upgrade head
uv run radioshaq run-api
```

### 2. Run the scheduler demo script

The script sends a message via POST /messages/process that asks to schedule a call (e.g. "Schedule a call for FLABC-1 with F1XYZ-1 at 1600 UTC on 40m"). The orchestrator should route to the scheduler agent.

```bash
cd radioshaq
uv run python scripts/demo/run_scheduler_demo.py \
  --base-url http://localhost:8000
```

- **Expected**: HTTP 200 from /messages/process; reply mentions scheduling or success.
- **Success criteria**: Script exits 0. If DB is configured, a row may appear in coordination_events (you can check via DB client or a future list endpoint).

### 3. Manual process (scheduling)

```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=DEMO-01" | jq -r .access_token)
curl -s -X POST "http://localhost:8000/messages/process" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"message":"Schedule a call for FLABC-1 with F1XYZ-1 tomorrow at 16:00 UTC on 40m."}'
```

## See also

- [coverage-matrix.md](coverage-matrix.md) — Scheduler row.
- [demo-orchestrator-judge.md](demo-orchestrator-judge.md) — How the orchestrator routes to agents.
