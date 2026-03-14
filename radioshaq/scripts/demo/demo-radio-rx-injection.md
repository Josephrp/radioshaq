# Radio RX injection demo (queue-based, no RF hardware)

This demo exercises **injection-queue reception**: `RadioReceptionAgent` (`radio_rx`) consuming messages from the injection queue with band-aware filtering. No HackRF or rig required.

## What you get

- **HQ** with orchestrator and **band listener** (or a one-off monitor task) running.
- Messages injected via `POST /inject/message` or `POST /messages/inject-and-store` appear in the RX path for the matching band.
- **Band-aware**: If the listener is monitoring 40m, only injected messages for 40m (or no band) are consumed; others can be left for other bands.

## Prerequisites

- **HQ API** running with message bus and orchestrator (so inject can optionally publish to bus).
- **Band listener** enabled **or** run the demo script that starts a short monitor via the orchestrator (if such an entry point exists). Alternatively, use the inject endpoints and then poll `/transcripts` to confirm stored injects.
- **JWT** via `POST /auth/token`.

## Steps

### 1. Start HQ

```bash
cd radioshaq
uv run radioshaq run-api
```

For band listener (optional): set `radio.listener_enabled=true` and `radio.listen_bands` (e.g. `[40m, 2m]`).

### 2. Run the injection demo script

The script injects a sequence of messages (different bands/callsigns) via `POST /inject/message` and optionally `POST /messages/inject-and-store`, then verifies they appear in transcripts or in the queue.

```bash
cd radioshaq
uv run python scripts/demo/run_radio_rx_injection_demo.py \
  --base-url http://localhost:8000 \
  --injections 5
```

- **Expected**: All injections return 200; transcript list (if stored) includes the injected messages.
- **Success criteria**: Script exits 0; injection responses report `ok: true`; GET /transcripts shows the new entries when inject-and-store is used.

### 3. Manual injection examples

```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token?subject=op1&role=field&station_id=DEMO-01" | jq -r .access_token)

# Inject into queue (no store)
curl -s -X POST "http://localhost:8000/inject/message" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"K5ABC de W1XYZ test on 40m","band":"40m","source_callsign":"K5ABC","destination_callsign":"W1XYZ"}'

# Inject and store (transcript DB)
curl -s -X POST "http://localhost:8000/messages/inject-and-store" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"text":"Stored inject 40m","band":"40m","source_callsign":"K5ABC","destination_callsign":"W1XYZ"}'
```

## See also

- [coverage-matrix.md](coverage-matrix.md) — Radio RX injection row.
- [inject_audio.py](inject_audio.py) — Standalone inject/relay script.
