# GIS location and propagation demo

This demo exercises **operator location** storage, **operators nearby** spatial query, and **propagation** (distance and band suggestions). Data is stored in PostGIS; the orchestrator can use GIS tools (set_operator_location, get_operator_location, operators_nearby) when processing messages.

## What you get

- **POST /gis/location**: Store operator location (callsign + latitude, longitude; source=user_disclosed).
- **GET /gis/location/{callsign}**: Retrieve latest stored location for a callsign.
- **GET /gis/operators-nearby**: Find operators within a radius of a point (from persisted operator_locations).
- **GET /radio/propagation**: Distance and suggested bands between two points (no DB; haversine + band rules).
- **POST /messages/process**: Optional — send a propagation or “who is near me” message; orchestrator may call GIS tools.

## How data is gathered and used

| Source | How | Where used |
|--------|-----|-------------|
| **User-disclosed** | POST /gis/location with lat/lon | Stored in `operator_locations` (PostGIS). Used by operators-nearby and by GIS agent for propagation origin when callsign is given. |
| **Orchestrator / LLM** | User says “my position is X” or “propagation from A to B”; tools `set_operator_location`, `get_operator_location`, `operators_nearby` | GISAgent and PropagationAgent; GET /radio/propagation is a direct API. |
| **Receiver / transcripts** | Optional: transcript with grid square or coords can drive inject + process, or a separate script posts location from parsed coords. | Same store; operators-nearby and propagation then use it. |

## Prerequisites

- **HQ API** with **Postgres + PostGIS** (DB required for location storage and operators-nearby).
- **JWT** via POST /auth/token.
- Optional: **Orchestrator + LLM** for process-based propagation / “who is near me” (POST /messages/process).

## Steps

### 1. Start HQ (with DB)

Ensure Postgres is running and migrations applied. Start the API so `/gis/*` and `/radio/propagation` are available.

### 2. Run the GIS demo script

```bash
cd radioshaq
uv run python scripts/demo/run_gis_demo.py --base-url http://localhost:8000
```

- **Expected**: POST /gis/location 200 for each callsign; GET /gis/location/{callsign} 200; GET /gis/operators-nearby 200; GET /radio/propagation 200.
- If DB is unavailable, location and operators-nearby return 503; script can still run propagation (no DB).

### 3. Optional: use recordings 13–16

With WAVs in `scripts/demo/recordings/` (see [option-c-recording-scripts.md](option-c-recording-scripts.md)):

- **13_set_operator_location.wav**: Upload via from-audio; then call POST /gis/location with coords (e.g. 37.77, -122.42) for the same callsign.
- **14_operators_nearby.wav**, **15_propagation_request.wav**: Use transcript text with POST /messages/process so the orchestrator uses GIS tools; or call GET /gis/operators-nearby and GET /radio/propagation directly with stored/fixed coords.
- **16_relay_with_location.wav**: Use for relay; optionally decode grid square and POST /gis/location.

## See also

- [option-c-recording-scripts.md](option-c-recording-scripts.md) — transcripts 13–16 (set location, operators nearby, propagation, relay with grid).
- [coverage-matrix.md](coverage-matrix.md) — GIS/Prop row.
- [README.md](README.md) — run_all_demos includes GIS demo.
