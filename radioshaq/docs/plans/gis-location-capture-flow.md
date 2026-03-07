# GIS Location Capture Flow — Implementation Plan

**Status:** Draft  
**Scope:** First-class location capture from user disclosure → extract → persist → reuse in GIS/propagation.  
**Non-goals (v1):** Live GPS streaming, full geocoding platform, UI map features.

---

## 1. Project Activities (High-Level)

| ID | Activity | Owner | Deps |
|----|----------|-------|------|
| A1 | **GIS REST API** — Add `api/routes/gis.py` with POST/GET location and GET operators-nearby | — | — |
| A2 | **DB & models** — Fix 0.0 coordinate bug, add lat/lon in responses, optional helper for latest location | — | — |
| A3 | **GIS agent** — Add `set_location` action; keep operators_nearby, get_location, propagation_prediction | — | — |
| A4 | **LLM GIS tools** — Implement and register set_operator_location, get_operator_location, operators_nearby | A2 | A1 (db) |
| A5 | **Orchestrator wiring** — Align agent name to `gis`, inject callsign, fallback origin from stored location | — | A2, A3 |
| A6 | **Reasoning prompt** — Location-disclosure → plan location-set first; use agent name `gis` | — | — |
| A7 | **Tests** — Unit tests for routes, storage, retrieval, 0.0, tools, agent routing, fallback | A1–A6 | — |
| A8 | **Docs** — OpenAPI and API docs for new GIS endpoints | A1 | — |

---

## 2. File-Level Tasks and Line-Level Subtasks

### 2.1 `radioshaq/radioshaq/api/routes/gis.py` (NEW)

**Purpose:** Public GIS location CRUD and operators-nearby.

| Task | Description | Line-level / subtasks |
|------|-------------|------------------------|
| **T1** | Create router and request/response models | • `APIRouter()`; • Pydantic models: `PostLocationBody` (callsign, latitude?, longitude?, location_text?, accuracy_meters?, altitude_meters?), `LocationResponse` (id, callsign, latitude, longitude, source, timestamp, confidence?), `OperatorsNearbyQuery` (latitude, longitude, radius_meters, recent_hours?, max_results?). |
| **T2** | Implement `POST /location` | • Depends: `get_db`, `get_current_user`. • Validate: require callsign; require either (latitude + longitude) or location_text. • **Strict v1:** If only `location_text` provided, return 400 with structured reason (e.g. `{"error": "ambiguous_location", "message": "Provide latitude and longitude for v1"}) or clarification prompt. • Normalize callsign to uppercase. • Bounds-check lat ∈ [-90, 90], lon ∈ [-180, 180]; allow 0.0. • Call `db.store_operator_location(callsign, lat, lon, ..., source="user_disclosed")`. • Return LocationResponse with id, normalized callsign, latitude, longitude, source, timestamp, confidence (e.g. 1.0 for explicit coords). |
| **T3** | Implement `GET /location/{callsign}` | • Depends: `get_db`, `get_current_user`. • Normalize path callsign to uppercase. • Call `db.get_latest_location(callsign)`; if None return 404. • Return response with explicit lat/lon (from helper or decoded geometry), not raw geometry. |
| **T4** | Implement `GET /operators-nearby` | • Query params: latitude, longitude, radius_meters, optional recent_hours, max_results. • Depends: `get_db`, `get_current_user`. • Call `db.find_operators_nearby(...)`; return list with distance_meters and client-safe fields (no raw geometry). |

**Dependencies:** `get_db` from `radioshaq.api.dependencies`; PostGISManager must expose/store with `source="user_disclosed"` and return decodable latest location.

---

### 2.2 `radioshaq/radioshaq/api/server.py`

| Task | Description | Line-level / subtasks |
|------|-------------|------------------------|
| **T5** | Register GIS router | • Import: `from radioshaq.api.routes import gis`. • Add: `app.include_router(gis.router, prefix="/gis", tags=["gis"])` (e.g. after radio router ~L285). |

---

### 2.3 `radioshaq/radioshaq/database/postgres_gis.py`

| Task | Description | Line-level / subtasks |
|------|-------------|------------------------|
| **T6** | Fix 0.0 coordinate bug in `store_coordination_event` | • Line ~451: change `if latitude and longitude` to `if latitude is not None and longitude is not None` so (0.0, 0.0) is stored. |
| **T7** | Add helper to return latest location with explicit lat/lon | • New method e.g. `get_latest_location_decoded(callsign) -> dict | None`: call existing `get_latest_location`, then decode geometry to latitude/longitude (from WKT/EWKT or GeoAlchemy2 shape); return dict with keys id, callsign, latitude, longitude, source, timestamp, altitude_meters, accuracy_meters, session_id. • Optionally refactor `get_latest_location` to use this and return same shape so all callers get lat/lon. |
| **T8** | Ensure store_operator_location accepts source="user_disclosed" | • Already has `source` parameter; no change if default is "manual". Callers pass `source="user_disclosed"`. |

**Note:** `OperatorLocation.to_dict()` currently returns `"location": self.location` (raw geometry). Either decode in PostGISManager when building response (T7) or extend model (see 2.4).

---

### 2.4 `radioshaq/radioshaq/database/models.py`

| Task | Description | Line-level / subtasks |
|------|-------------|------------------------|
| **T9** | Ensure location-facing API responses include lat/lon | • Option A: In `OperatorLocation.to_dict()`, if geometry is available, decode to latitude/longitude and add keys `latitude`, `longitude` (and optionally drop or keep `location` for internal use). • Option B: Keep model as-is; decoding only in PostGISManager helper (T7) and use that for API. Prefer Option B to avoid changing all existing `to_dict()` callers; API and GIS agent use the decoded helper. |

---

### 2.5 `radioshaq/radioshaq/specialized/gis_agent.py`

| Task | Description | Line-level / subtasks |
|------|-------------|------------------------|
| **T10** | Add `set_location` action | • In `execute()`, branch: `if action == "set_location": return await self._set_location(task, upstream_callback)`. • Implement `_set_location`: require callsign; require latitude/longitude (float); optional altitude_meters, accuracy_meters; normalize callsign; call `self.db.store_operator_location(callsign, lat, lon, altitude_meters=..., accuracy_meters=..., source="user_disclosed")`; emit result; return dict with success, id, callsign, latitude, longitude, source, timestamp. • Handle missing db: return success=False with message. |
| **T11** | Add capability for set_location | • Add to `capabilities`: e.g. `"set_operator_location"` or keep list as action-based; ensure agent can be selected for “set my location” tasks. |

---

### 2.6 `radioshaq/radioshaq/orchestrator/factory.py`

| Task | Description | Line-level / subtasks |
|------|-------------|------------------------|
| **T12** | Register GIS tools in create_tool_registry | • When `db is not None`, instantiate GIS tools (e.g. `SetOperatorLocationTool(db)`, `GetOperatorLocationTool(db)`, `OperatorsNearbyTool(db)`). • Call `registry.register(tool)` for each. • Log debug: "Registered GIS tools: set_operator_location, get_operator_location, operators_nearby". |

---

### 2.7 `radioshaq/radioshaq/specialized/gis_tools.py` (NEW — or under `orchestrator/tools` if preferred)

| Task | Description | Line-level / subtasks |
|------|-------------|------------------------|
| **T13** | Implement SetOperatorLocationTool | • name = `"set_operator_location"`, description = e.g. "Store the operator's current location (latitude, longitude) for later use in propagation and nearby queries." • to_schema(): parameters — callsign (required), latitude (required), longitude (required), optional altitude_meters, accuracy_meters. • validate_params: callsign non-empty, lat/lon in range, numeric. • execute: call db.store_operator_location(..., source="user_disclosed"); return JSON string with id, callsign, latitude, longitude, source, timestamp. |
| **T14** | Implement GetOperatorLocationTool | • name = `"get_operator_location"`, description = "Get the latest stored location for a callsign." • to_schema(): parameters — callsign (required). • execute: call db.get_latest_location (or get_latest_location_decoded); return JSON with location or "no location stored". |
| **T15** | Implement OperatorsNearbyTool | • name = `"operators_nearby"`, description = "Find operators within a radius of a point (latitude, longitude)." • to_schema(): parameters — latitude, longitude, radius_meters (optional default), optional recent_hours, max_results. • execute: call db.find_operators_nearby; return JSON list. |

**Placement:** Either `radioshaq/specialized/gis_tools.py` (alongside whitelist_tools, relay_tools) or `radioshaq/orchestrator/tools/gis_tools.py`; factory imports and registers them.

---

### 2.8 `radioshaq/radioshaq/orchestrator/react_loop.py`

| Task | Description | Line-level / subtasks |
|------|-------------|------------------------|
| **T16** | Align context injection agent name with registry | • Line ~457: change `if agent_name == "gis_agent"` to `if agent_name == "gis"` so callsign is injected when task is routed to the GIS agent (registered as `gis`). |
| **T17** | Fallback: use stored location when GIS task lacks origin | • In `_inject_agent_context`, when agent_name == "gis" and task_dict indicates propagation (e.g. action "propagation_prediction") and (latitude_origin, longitude_origin) are missing/zero but callsign is present: call db.get_latest_location(callsign) and if present set task_dict["latitude_origin"], task_dict["longitude_origin"] from decoded location. • Requires db available in orchestrator (e.g. from app state or passed into REACTOrchestrator); ensure create_orchestrator or react_loop has access to db for this injection. |

**Note:** If orchestrator does not currently have `db` in scope, add it (e.g. REACTOrchestrator.__init__(..., db=None) and pass from factory).

---

### 2.9 `radioshaq/radioshaq/orchestrator/registry.py`

| Task | Description | Line-level / subtasks |
|------|-------------|------------------------|
| **T18** | Update docstring/examples to use agent name `gis` | • Lines ~59, 63: replace "gis_agent" with "gis" in comments so planners and future code use the correct name. |

---

### 2.10 `radioshaq/prompts/orchestrator/phases/reasoning.md`

| Task | Description | Line-level / subtasks |
|------|-------------|------------------------|
| **T19** | Add location-disclosure guidance | • In "Tasks" or "Remember" section: "If the user discloses their location (e.g. 'I'm at 48.8566, 2.3522' or 'I'm in Lyon'), plan a location-set action first (e.g. use tool set_operator_location or a gis task set_location) before any GIS/propagation reasoning that uses origin." |
| **T20** | Use agent name `gis` in examples | • Line ~26: change "gis_agent" to "gis" in the example agent list. |

---

### 2.11 `radioshaq/radioshaq/api/routes/radio.py`

| Task | Description | Line-level / subtasks |
|------|-------------|------------------------|
| **T21** | (Optional) Allow propagation to use stored origin | • If query params lat_origin/lon_origin omitted but e.g. callsign provided, call get_latest_location(callsign) and use as origin; else 400. Document in OpenAPI. |

**Scope:** Optional for v1; can be deferred so that propagation always requires explicit coords at the REST layer; fallback only in orchestrator/agent layer.

---

### 2.12 Tests

| Task | Description | Line-level / subtasks |
|------|-------------|------------------------|
| **T22** | Unit tests: GIS API routes | • New file e.g. `tests/unit/test_gis_routes.py` or under `tests/unit/api/`. • Test POST /gis/location with valid lat/lon → 200, body has id, latitude, longitude, source=user_disclosed. • Test POST with 0.0, 0.0 → stored and returned. • Test GET /gis/location/{callsign} → 200 with lat/lon; 404 when no location. • Test GET /gis/operators-nearby with mock db → 200 and list. • Test POST with only location_text (v1 strict) → 400 and structured error. • Use mocked get_db / TestClient. |
| **T23** | Unit tests: store_coordination_event 0.0 | • In existing or new DB test file: call store_coordination_event with latitude=0.0, longitude=0.0; assert event stored with non-null location (or equivalent). |
| **T24** | Unit tests: Tool registry contains GIS tools | • In test_orchestrator or new test: create_tool_registry(config, db=db, app=app); assert "set_operator_location", "get_operator_location", "operators_nearby" in registry.tool_names. |
| **T25** | Unit tests: Agent routing and context injection for gis | • Decomposed task with agent "gis" and no callsign in payload; inject context with callsign; assert task_dict["callsign"] set. • Optionally assert get_agent_for_task({"agent": "gis"}) returns GISAgent. |
| **T26** | Unit tests: Stored location as fallback origin | • When propagation task has no latitude_origin/longitude_origin but has callsign, and db has stored location for that callsign, assert task_dict gets latitude_origin/longitude_origin from stored location. |

---

### 2.13 Documentation

| Task | Description | Line-level / subtasks |
|------|-------------|------------------------|
| **T27** | OpenAPI and API docs | • Regenerate or manually add to `docs/api/openapi.json`: paths `/gis/location`, `/gis/location/{callsign}`, `/gis/operators-nearby` with request/response schemas. • Document: v1 strict (location_text alone returns 400), 0.0 valid, source and timestamp in response. |

---

## 3. Acceptance Criteria Checklist

- [ ] User can submit explicit lat/lon via `POST /gis/location` and retrieve same via `GET /gis/location/{callsign}`.
- [ ] `operators_nearby` (API and tool) returns results from persisted operator_locations.
- [ ] Propagation/GIS tasks can use stored disclosed location as origin when origin coords omitted (orchestrator/agent fallback).
- [ ] Ambiguous `location_text` (v1 strict) returns 400 with structured reason or clarification.
- [ ] 0.0 coordinates are valid and persisted (store_coordination_event and store_operator_location).
- [ ] Audit: stored records include source (`user_disclosed`) and timestamp.
- [ ] Unit tests cover: parsing, storage, retrieval, 0.0 handling, tool registration, agent routing, fallback behavior.

---

## 4. Risk Mitigation

- **Incorrect extraction from vague text:** v1 strict mode: require explicit lat/lon for storage; optional v2 geocode with confidence + confirmation.
- **Agent naming mismatch:** Unify on `gis` everywhere (react_loop, reasoning.md, registry docstring); no alias needed if prompt and code both use `gis`.

---

## 5. Implementation Order (Suggested)

1. **DB & models** (T6, T7, T9) — fix bug and decoding so API and agent can return lat/lon.
2. **GIS API** (T1–T4, T5) — routes and server registration.
3. **GIS agent set_location** (T10, T11) — agent action for orchestrated flow.
4. **GIS tools** (T13–T15, T12) — LLM tool-calling and factory registration.
5. **Orchestrator** (T16, T17, T18) — context injection and fallback; pass db into orchestrator if needed.
6. **Reasoning prompt** (T19, T20).
7. **Tests** (T22–T26).
8. **Docs** (T27).
9. **Optional** (T21) — propagation endpoint fallback to stored origin.

---

## 6. Key Code Anchors (Reference)

| Area | File:Line | Note |
|------|-----------|------|
| Request entry | messages.py:38, 54, 62 | process_message, callsign from body/user |
| Task decomposition | react_loop.py:471, 482, 507 | REASONING phase, decomposed_tasks |
| Context injection | react_loop.py:451–459 | callsign injection for whitelist, gis, scheduler |
| Agent execution | react_loop.py:605, 628, 631 | _inject_agent_context, get_agent_for_task, execute |
| GIS agent actions | gis_agent.py:30, 48, 87, 128 | name, execute branches, _get_location |
| PostGIS | postgres_gis.py:100, 139, 176, 214, 451 | store_operator_location, find_operators_nearby, get_latest_location, store_coordination_event |
| Propagation route | radio.py:23, 32 | GET /radio/propagation, propagation_prediction |
| Tool registry | factory.py:332, 344, 354, 369 | create_tool_registry, whitelist/memory/relay registration |
| Agent registry | registry.py:54, 63 | get_agent_for_task, agent name docstring |

---

*End of plan.*
