# Comprehensive Plan: Callsign Registration, Audio Routes, Radio Audio-In/Out

Structured for agent execution: **Projects** → **Activities** → **File-level tasks** → **Line-level subtasks**.

---

## Design decisions

- **Registered callsigns**: Stored in DB table `registered_callsigns`; effective whitelist = `config.allowed_callsigns` (optional static list) ∪ registered callsigns. New callsigns can be registered via API or via audio (ASR extracts or user says callsign); once registered, they are **automatically accepted** for store/relay/inject+store.
- **All new routes**: Centralized under `/messages` and `/transcripts` (and one under `/radio`) for easy access; see route index below.
- **Radio out = audio**: Responses to radio-in are always sent as **audio** over radio (TTS → radio_tx). Ensure default is `use_tts=True` and that play-over-radio endpoints use TTS.
- **Optional audio activation**: When enabled, the voice pipeline requires an **activation phrase** (e.g. "radioshaq" or configurable) in the first segment before processing further; otherwise treat as passive listen-only until activated.

---

## Route index (target)

| Method | Path | Purpose |
|--------|------|--------|
| POST | `/messages/from-audio` | Upload audio → ASR → whitelist/registration check → store (+ optional inject) |
| POST | `/messages/inject-and-store` | Text + optional audio path → whitelist check → inject queue + DB store |
| POST | `/messages/relay` | (Existing) Band relay; add whitelist/registration check |
| GET | `/transcripts` | (Existing) Search; optional whitelist filter |
| GET | `/transcripts/{id}` | Get one transcript by id (for play) |
| POST | `/transcripts/{id}/play` | Load transcript → TTS → send via radio (audio out) |
| POST | `/radio/send-tts` | Send arbitrary text as TTS over radio (audio out) |
| GET | `/callsigns/registered` | List registered callsigns |
| POST | `/callsigns/register` | Register a callsign (body: `callsign`, optional `source: "api" \| "audio"`) |
| POST | `/callsigns/register-from-audio` | Upload audio → ASR → extract/require callsign → register and return it |
| DELETE | `/callsigns/registered/{callsign}` | Remove callsign from registry (optional, for admin) |

---

# PROJECT 1: Callsign registration and auto-accept whitelist

**Goal**: Agent can register new callsigns (API or audio); effective whitelist = config list ∪ registered; all store/relay/inject+store paths accept callsigns that are in the effective whitelist.

---

## Activity 1.1: Database and config for registered callsigns

### File-level task 1.1.1: Add `RegisteredCallsign` model and table

**File**: `radioshaq/radioshaq/database/models.py`

- **Line-level subtasks**:
  - After `OperatorLocation` class (or before `Transcript`), add new class `RegisteredCallsign(Base)`.
  - Add `__tablename__ = "registered_callsigns"`.
  - Add columns: `id` (Integer, PK), `callsign` (String(20), unique, index, nullable=False), `source` (String(20), default `"api"`), `created_at` (DateTime(timezone=True), server_default=now()).
  - Add `to_dict(self)` returning `{"id", "callsign", "source", "created_at"}`.

**File**: `radioshaq/infrastructure/local/alembic/versions/` (new migration)

- **Line-level subtasks**:
  - Create new migration file `YYYY_MM_DD_0002-registered_callsigns.py`.
  - In `upgrade()`: `op.create_table("registered_callsigns", sa.Column("id", sa.Integer(), nullable=False), sa.Column("callsign", sa.String(20), nullable=False), sa.Column("source", sa.String(20), server_default="api"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("callsign"))`; `op.create_index("ix_registered_callsigns_callsign", "registered_callsigns", ["callsign"])`.
  - In `downgrade()`: `op.drop_table("registered_callsigns")`.

### File-level task 1.1.2: Config for static whitelist and activation

**File**: `radioshaq/radioshaq/config/schema.py`

- **Line-level subtasks**:
  - In `RadioConfig`, after `restricted_bands_region`, add `allowed_callsigns: list[str] | None = Field(default=None, description="Static list; merged with DB registered_callsigns. None = only DB registry (or allow all if no registry).")`.
  - Add `callsign_registry_required: bool = Field(default=False, description="If True, only registered or config-allowed callsigns accepted. If False, allow all when both allowed_callsigns and DB are empty.")`.
  - In `AudioConfig`, after `trigger_callsign`, add `audio_activation_enabled: bool = Field(default=False)` and `audio_activation_phrase: str = Field(default="radioshaq", description="Phrase that must be heard before processing (when audio_activation_enabled).")`.
  - Add `@field_validator("allowed_callsigns", mode="before")` on RadioConfig (or model validator) to normalize list elements to `.strip().upper()` and filter empty strings.

---

## Activity 1.2: Persistence layer for registered callsigns

### File-level task 1.2.1: PostGISManager methods for registered callsigns

**File**: `radioshaq/radioshaq/database/postgres_gis.py`

- **Line-level subtasks**:
  - Add `async def list_registered_callsigns(self) -> list[dict[str, Any]]`: select all from `registered_callsigns`, order by `created_at` desc, return list of `to_dict()`.
  - Add `async def register_callsign(self, callsign: str, source: str = "api") -> int`: normalize callsign to upper, insert if not exists (on conflict do nothing or return existing id), return id.
  - Add `async def unregister_callsign(self, callsign: str) -> bool`: delete where callsign=normalized, return rowcount > 0.
  - Add `async def is_callsign_registered(self, callsign: str) -> bool`: select exists where callsign=normalized.

(If PostGISManager is not used for this table, add a small `RegisteredCallsignStore` protocol and implementation that uses the same table; keep interface in `database/transcripts.py` or new `database/callsigns.py`.)

### File-level task 1.2.2: Effective whitelist helper

**File**: `radioshaq/radioshaq/api/callsign_whitelist.py` (new file)

- **Line-level subtasks**:
  - Define `async def get_effective_allowed_callsigns(db, config: RadioConfig) -> set[str]`: if config.allowed_callsigns is not None, start with set(normalized); else start with empty set. If db and hasattr(db, "list_registered_callsigns"), call it and add each `c["callsign"]` to the set. Return set.
  - Define `def is_callsign_allowed(callsign: str | None, allowed: set[str], registry_required: bool) -> bool`: if callsign is None or empty, return False. Normalize to upper. If allowed is non-empty and callsign not in allowed, return False. If registry_required and allowed is empty, return False (no one allowed). Return True.
  - Export both for use in routes.

---

## Activity 1.3: API routes for registration and list

### File-level task 1.3.1: Registered callsigns routes

**File**: `radioshaq/radioshaq/api/routes/callsigns.py` (new file)

- **Line-level subtasks**:
  - Create APIRouter(); add `get_current_user` dependency.
  - `GET ""`: list registered. Depends(get_db), get_config. If db is None, return `{"registered": [], "count": 0}`. Else call db.list_registered_callsigns(), return `{"registered": list, "count": len(list)}`.
  - `POST "/register"`: body `{ "callsign": str, "source": "api" | "audio" }`. Validate callsign format (e.g. 3–7 chars + optional -digit). Depends(get_db), get_config. If db is None, raise 503. Call db.register_callsign(callsign, source). Return `{"ok": True, "callsign": normalized, "id": id}`.
  - `POST "/register-from-audio"`: accept multipart file (audio). Run ASR (transcribe_audio_voxtral) in thread/run_in_executor. Parse callsign from transcript (e.g. first word or regex for callsign pattern) or require query param `callsign` to confirm. Call register_callsign. Return `{"ok": True, "callsign": normalized, "transcript": transcript}`.
  - `DELETE "/registered/{callsign}"`: path callsign. Depends(get_db). If db is None, 503. Call unregister_callsign; if False, 404. Return `{"ok": True}`.

**File**: `radioshaq/radioshaq/api/server.py`

- **Line-level subtasks**:
  - Import `callsigns` router; `app.include_router(callsigns.router, prefix="/callsigns", tags=["callsigns"])`.

---

# PROJECT 2: Message persistence routes (from-audio, inject-and-store, relay whitelist)

**Goal**: New routes for storing messages from audio and from text; relay and inject+store enforce effective whitelist (config + registered).

---

## Activity 2.1: Shared storage and whitelist in message routes

### File-level task 2.1.1: Transcript storage and whitelist dependency

**File**: `radioshaq/radioshaq/api/routes/relay.py`

- **Line-level subtasks**:
  - Import `get_effective_allowed_callsigns`, `is_callsign_allowed` from `radioshaq.api.callsign_whitelist` (or equivalent).
  - After parsing `source_callsign` and `destination_callsign` (existing lines ~75–76), add: get config.radio; `allowed = await get_effective_allowed_callsigns(request.app.state.db, config.radio)`; `if not is_callsign_allowed(source_callsign, allowed, config.radio.callsign_registry_required): raise HTTPException(403, "Source callsign not allowed")`; if destination_callsign and not is_callsign_allowed(destination_callsign, allowed, ...): same 403. Place before the `if not storage` block.

### File-level task 2.2.2: POST /messages/from-audio

**File**: `radioshaq/radioshaq/api/routes/messages.py` (extend existing)

- **Line-level subtasks**:
  - Add dependency `get_db`, `get_config`; import `TranscriptStorage`, `get_effective_allowed_callsigns`, `is_callsign_allowed`; import `transcribe_audio_voxtral` from `radioshaq.audio.asr`; import `get_injection_queue` from `radioshaq.radio.injection`.
  - Add route `@router.post("/from-audio")` with `request: Request`, `user: TokenPayload = Depends(get_current_user)`. Accept multipart: `file: UploadFile`, form fields `source_callsign: str`, `destination_callsign: str | None = None`, `band: str | None = None`, `mode: str = "PSK31"`, `frequency_hz: float = 0`, `session_id: str | None = None`, `inject: bool = False`. Limit file size (e.g. 10 MB) and validate content type (audio/* or application/octet-stream).
  - In route body: read file to temp path; run ASR in `asyncio.to_thread(transcribe_audio_voxtral, path, ...)` or run_in_executor; get config.radio, `allowed = await get_effective_allowed_callsigns(getattr(request.app.state, "db", None), config.radio)`; `is_callsign_allowed(source_callsign, allowed, config.radio.callsign_registry_required)` or 403; same for destination_callsign if provided.
  - Get storage via same pattern as relay (`_get_transcript_storage(request)` or inline); if storage and db, get band plan default freq if frequency_hz 0; `metadata = {"band": band, "source": "from_audio"}`; `transcript_id = await storage.store(session_id=..., source_callsign=..., frequency_hz=..., mode=..., transcript_text=transcript_text, destination_callsign=..., metadata=metadata, raw_audio_path=temp_path or None)`.
  - If `inject` is True, call `get_injection_queue().inject_message(text=transcript_text, band=band, frequency_hz=..., mode=..., source_callsign=..., destination_callsign=...)`. Return `{"ok": True, "transcript_id": transcript_id, "transcript_text": transcript_text, "injected": inject}`.

### File-level task 2.2.3: POST /messages/inject-and-store

**File**: `radioshaq/radioshaq/api/routes/inject.py` (extend) or **File**: `radioshaq/radioshaq/api/routes/messages.py`

- **Line-level subtasks**:
  - Add route `POST /messages/inject-and-store` (in messages.py): body same as InjectMessageBody (text, band, frequency_hz, mode, source_callsign, destination_callsign, audio_path, metadata). Depends: get_db, get_config, get_current_user.
  - Get effective allowed set; `is_callsign_allowed(source_callsign or "UNKNOWN", allowed, config.radio.callsign_registry_required)` and same for destination; 403 if not allowed.
  - Get TranscriptStorage(request); if storage, call storage.store(...) with same fields, metadata `{"source": "inject_and_store"}`. Always call `get_injection_queue().inject_message(...)`.
  - Return `{"ok": True, "transcript_id": transcript_id or None, "qsize": queue.qsize()}`.

(Alternatively implement as `POST /inject/message` with body field `store: bool = False` and same logic inside inject.py; then no new path but same behavior.)

---

# PROJECT 3: Audio-in, audio-out (responses as audio; optional audio activation)

**Goal**: Responses to radio are sent as audio on radio out; optionally require an audio activation phrase before processing.

---

## Activity 3.1: Ensure radio responses are always audio out

### File-level task 3.1.1: Default TTS for radio response

**File**: `radioshaq/radioshaq/specialized/radio_rx_audio.py`

- **Line-level subtasks**:
  - In `_send_response`, ensure task dict always includes `"use_tts": True` (already present at line ~344). Add comment: "# Responses to radio are always sent as audio (TTS) on radio out."
  - If `response_agent` is radio_tx, verify no path sends text-only; if there is a path that does not set use_tts, set it to True by default.

### File-level task 3.1.2: Play-over-radio and send-tts routes (audio out)

**File**: `radioshaq/radioshaq/api/routes/transcripts.py`

- **Line-level subtasks**:
  - Add `get_agent_registry` or get radio_tx from app state (e.g. dependency that returns registry.get_agent("radio_tx")).
  - Add `GET "/{transcript_id:int}"`: get_db, get_current_user. Load transcript by id (add PostGISManager method `get_transcript_by_id(id) -> dict | None` if not present). If not found, 404. Return transcript dict.
  - Add `POST "/{transcript_id:int}/play"`: get transcript by id; if not found, 404. Get radio_tx agent. Run TTS: `text_to_speech_elevenlabs(transcript["transcript_text"], output_path=temp_file)`. Build task `{"transmission_type": "voice", "message": transcript["transcript_text"], "audio_path": temp_file}` or use_tts=True and message. Execute agent.execute(task). Return `{"ok": True, "transcript_id": transcript_id}`. Clean up temp file.

**File**: `radioshaq/radioshaq/api/routes/radio.py`

- **Line-level subtasks**:
  - Add `POST "/send-tts"`: body `{"message": str, "frequency_hz": float | None, "mode": str | None}`. Depends get_agent_registry, get_current_user. Get radio_tx agent; task = `{"transmission_type": "voice", "message": body.message, "use_tts": True}`; optional frequency/mode in task if supported. Execute. Return `{"ok": True}`.

### File-level task 3.1.3: PostGISManager get_transcript_by_id

**File**: `radioshaq/radioshaq/database/postgres_gis.py`

- **Line-level subtasks**:
  - Add `async def get_transcript_by_id(self, transcript_id: int) -> dict[str, Any] | None`: select Transcript where id=transcript_id; if no row, return None; else return row.to_dict().

---

## Activity 3.2: Optional audio activation

### File-level task 3.2.1: Activation state and phrase check in radio_rx_audio

**File**: `radioshaq/radioshaq/specialized/radio_rx_audio.py`

- **Line-level subtasks**:
  - In `RadioAudioReceptionAgent.__init__` or at start of monitoring, add instance flag `_audio_activated: bool = False` (reset to False when monitoring starts if activation is enabled).
  - In `_on_segment_ready`, after transcript is obtained and before trigger_filter.check: if `self.config.audio_activation_enabled` and not `self._audio_activated`: check if `self.config.audio_activation_phrase.lower() in transcript.lower()`; if yes, set `self._audio_activated = True` and optionally emit progress "activated"; if no, return without processing (do not run trigger_filter or response flow).
  - When monitoring stops (e.g. in the method that sets _monitoring = False), set `_audio_activated = False` so next session requires activation again.

---

# PROJECT 4: Retrieval and playback (API + radio)

**Goal**: Transcripts retrievable by API; play-over-radio and send-tts for audio out. Optional whitelist filter on GET /transcripts.

---

## Activity 4.1: Transcript retrieval and optional whitelist filter

### File-level task 4.1.1: GET /transcripts filter by effective whitelist

**File**: `radioshaq/radioshaq/api/routes/transcripts.py`

- **Line-level subtasks**:
  - In `search_transcripts`, after `results = await storage.search(...)` and `out = list(results)`, if config.radio.allowed_callsigns is not None or (get_db and has list_registered_callsigns): `allowed = await get_effective_allowed_callsigns(db, config.radio)`. If `allowed` is non-empty, filter `out` to only items where `(t.get("source_callsign") in allowed or t.get("destination_callsign") in allowed)` (or source_callsign only, per policy). Then apply existing band filter if band. Return `{"transcripts": out, "count": len(out)}`.

### File-level task 4.1.2: GET /transcripts/{id} (already specified in 3.1.2)

- Covered under Activity 3.1.2.

---

# PROJECT 5: Wire new routes and dependencies

**Goal**: All new routes registered; dependencies (get_db, get_config, storage, agent registry) available where needed.

---

## Activity 5.1: Server and dependency wiring

### File-level task 5.1.1: Register routers and ensure prefix consistency

**File**: `radioshaq/radioshaq/api/server.py`

- **Line-level subtasks**:
  - Ensure `messages.router` is mounted at `/messages` (already is).
  - Ensure `transcripts.router` at `/transcripts` (already is).
  - Add `app.include_router(callsigns.router, prefix="/callsigns", tags=["callsigns"])`.
  - Ensure `radio.router` includes new `POST /send-tts` (in radio.py).

### File-level task 5.1.2: Transcript storage helper reuse

**File**: `radioshaq/radioshaq/api/routes/messages.py` and **relay.py**

- **Line-level subtasks**:
  - Extract or share `_get_transcript_storage(request)` (e.g. in a shared `radioshaq.api.dependencies` or `radioshaq.api.storage`) so both relay and messages.from_audio use the same helper. If keeping in relay, messages can import from relay or duplicate one-liner.

---

# Execution order (recommended)

1. **Project 1** (callsign registration and whitelist): 1.1 → 1.2 → 1.3 so DB and config exist before routes.
2. **Project 2** (message persistence): 2.1 (relay whitelist) → 2.2 (from-audio, inject-and-store).
3. **Project 3** (audio out + activation): 3.1 (TTS default, play + send-tts routes, get_transcript_by_id) → 3.2 (activation).
4. **Project 4** (retrieval filter): 4.1 after 1.2 (effective whitelist available).
5. **Project 5** (wiring): 5.1 after all new routes exist.

---

# Checklist summary

- [x] **1.1.1** models: RegisteredCallsign; **1.1.2** migration registered_callsigns; **1.1.3** config: allowed_callsigns, callsign_registry_required, audio_activation_*.
- [x] **1.2.1** PostGISManager: list_registered_callsigns, register_callsign, unregister_callsign, is_callsign_registered; **1.2.2** callsign_whitelist.py: get_effective_allowed_callsigns, is_callsign_allowed.
- [x] **1.3.1** callsigns.py: GET list, POST register, POST register-from-audio, DELETE registered/{callsign}; server.py include_router callsigns.
- [x] **2.1.1** relay.py: whitelist check before store; **2.2.2** messages.py: POST /from-audio; **2.2.3** messages.py: POST /inject-and-store (or inject with store=true).
- [x] **3.1.1** radio_rx_audio: ensure use_tts True; **3.1.2** transcripts: GET /{id}, POST /{id}/play; radio.py POST /send-tts; **3.1.3** postgres_gis: get_transcript_by_id.
- [x] **3.2.1** radio_rx_audio: _audio_activated and activation phrase check in _on_segment_ready.
- [x] **4.1.1** transcripts search: filter by effective whitelist when set.
- [x] **5.1** server: all routers; shared storage helper (get_transcript_storage, get_radio_tx_agent in dependencies).

**Migrations:** Use `python infrastructure/local/run_alembic.py upgrade head` (see [docs/database.md](database.md)).
