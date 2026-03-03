# Whitelist Callsigns + Audio→Text→Store + Retrieval (API & Radio)

Investigation: how to use existing radio and audio infrastructure to (1) whitelist callsigns, (2) save messages from audio (ASR) and text (existing routes), and (3) make messages retrievable both via API and over the radio.

---

## 1. Current infrastructure

### 1.1 Audio → text (ASR) and text → audio (TTS)

| Piece | Location | Notes |
|------|----------|--------|
| **ASR** | `radioshaq/audio/asr.py` | `transcribe_audio_voxtral()` — Voxtral (shakods/voxtral-asr-en). Used by demo script and by `radio_rx_audio` for live segments and `transcribe_file` action. |
| **TTS** | `radioshaq/audio/tts.py` | `text_to_speech_elevenlabs()` — ElevenLabs API. Used by `radio_tx` when `use_tts=True` (config `voice_use_tts` or task). |
| **Voice RX pipeline** | `radio_rx_audio.py` | Capture → VAD → ASR per segment → trigger filter (`trigger_callsign` + `trigger_phrases`) → pending response or auto-respond. Does **not** write to transcript DB. |
| **Demo script** | `scripts/demo/inject_audio.py` | Can run ASR on file (`--stt --asr voxtral`) then call `POST /inject/message` (and optionally `POST /messages/relay`). No HTTP route that does “upload audio → ASR → store” in one call. |

There are **no HTTP routes** that accept audio and return or store transcript; ASR is used inside agents and in the CLI script only.

### 1.2 Radio routes

| Route | Purpose |
|-------|--------|
| `POST /inject/message` | Push text (and optional audio path) into **in-memory** injection queue. Consumed by `radio_rx` in demo mode. **Does not persist.** |
| `POST /messages/relay` | Store **two** transcripts (source band + relayed band) via `TranscriptStorage` → Postgres. Only API path that **persists** messages. |
| `GET /transcripts` | Search stored transcripts by `callsign`, `band`, `frequency_*`, `mode`, `since`, `limit`. Used so “User B” can poll messages for their callsign. |
| `GET /radio/bands` | List bands. |
| `GET /radio/propagation` | Propagation prediction. |

So: **persistent storage** is only done in `/messages/relay`. Inject is ephemeral (queue only).

### 1.3 “Whitelist” today

- **Compliance** (`radio/compliance.py`): TX **band** restrictions (FCC §15.205, amateur bands only). No callsign allowlist.
- **Trigger filter** (`radio_rx_audio`): `trigger_callsign` (single callsign) and `trigger_phrases` — used to decide whether to **process** a live transcript (e.g. respond). Not used for persistence or for accepting/rejecting API submissions.
- **Config** (`config/schema.py`): `RadioConfig` has `tx_audit_log_path`, `tx_allowed_bands_only`, etc. No `allowed_callsigns` or similar.

There is **no callsign whitelist** that gates which messages are accepted or stored.

### 1.4 Transcript storage

- **Interface**: `TranscriptStorage` in `database/transcripts.py` — `store()`, `search()`.
- **Backend**: `PostGISManager.store_transcript()` / `search_transcripts()` in `database/postgres_gis.py`.
- **Model**: `Transcript` — `session_id`, `source_callsign`, `destination_callsign`, `frequency_hz`, `mode`, `transcript_text`, `raw_audio_path`, `extra_data` (e.g. band, relay metadata).

Retrieval by API: `GET /transcripts?callsign=...&band=...`. Retrieval “by radio” today means: (1) if the message was **injected** (not stored), only an active `radio_rx` on the injection queue sees it; (2) if the message was **relayed** (stored), the recipient must **poll** `GET /transcripts` — there is no automatic “play over radio” for stored messages.

---

## 2. Goals (summary)

1. **Whitelist callsigns**: Only accept/store messages where source (and optionally destination) callsign is in a configured allowlist.
2. **Save messages from audio**: Use existing ASR + transcript storage so that audio (e.g. uploaded file or future stream) becomes text and is stored, with whitelist enforced.
3. **Save messages from existing routes**: Apply whitelist to existing paths that can persist: relay; and optionally inject (if we add “inject + store”).
4. **Retrieval by API**: Already satisfied by `GET /transcripts`; optionally restrict results to whitelisted callsigns only.
5. **Retrieval by radio**: (a) Stored messages are already visible to anyone polling `GET /transcripts?callsign=...`. (b) Optionally: “play message over radio” = fetch transcript → TTS → send via existing radio_tx (e.g. approve-style flow or dedicated “playback” endpoint).

---

## 3. Proposed implementation

### 3.1 Callsign whitelist (config)

- Add to **RadioConfig** (or a small **MessagesConfig** if you prefer to keep radio vs messaging separate):

```python
# In config/schema.py (e.g. under RadioConfig or new MessagesConfig)
allowed_callsigns: list[str] | None = Field(
    default=None,
    description="If set, only these callsigns are accepted as source/destination for storing or relaying messages. None = allow all.",
)
```

- Normalize to uppercase when loading (e.g. in validator or at use site). Empty list `[]` = allow none (reject all).

### 3.2 Enforce whitelist wherever messages are stored

- **Relay** (`api/routes/relay.py`): Before calling `storage.store()` twice, check:
  - `source_callsign` in `allowed_callsigns` (if list is set).
  - If `destination_callsign` is provided, optionally require it in `allowed_callsigns` as well (or only source).
  - If not allowed → `HTTPException(403, "Callsign not allowed")`.
- **New “store-only” or “audio → store” route** (below): Same checks before storing.

No need to change inject queue logic for “whitelist” unless we also add “inject + store” (then that path would enforce whitelist before writing to DB).

### 3.3 New route: audio → ASR → store (and optional inject)

Add a route that:

1. Accepts **audio** (file upload or URL/path if internal).
2. Runs **ASR** (reuse `transcribe_audio_voxtral` from `audio/asr.py`; fallback to whisper if desired).
3. Requires (or parses) **source_callsign** (and optionally **destination_callsign**, **band**, **mode**). Parsing from transcript text is optional (e.g. “K5ABC de W1XYZ” → source K5ABC, dest W1XYZ) but risky; better to require in body.
4. **Whitelist check**: source (and dest if used) must be in `allowed_callsigns` if config is set.
5. **Store** via `TranscriptStorage.store()` (same shape as relay: session_id, source_callsign, frequency_hz, mode, transcript_text, destination_callsign, metadata e.g. band, `extra_data`).
6. Optional: **inject** the same message into `get_injection_queue()` so that any active `radio_rx` (demo mode) also sees it without a separate inject call.

Suggested path: `POST /messages/from-audio` (or `POST /inject/audio-and-store`). Request: multipart file or base64 audio; form/JSON fields: `source_callsign`, `destination_callsign` (optional), `band`, `mode`, `frequency_hz`, `session_id` (optional). Response: `transcript_id`, `transcript_text`, optional `injected: true`.

Implementation details:

- Use `get_db(request)` and `_get_transcript_storage(request)` pattern from relay (or a shared helper).
- Use `get_config(request)` to read `allowed_callsigns`.
- ASR: call `transcribe_audio_voxtral` (or wrap in async/thread if needed). Limit file size and duration for DoS safety.
- Reuse `Transcript` fields; set `extra_data = {"band": band, "source": "from_audio"}` so you can filter later.

This gives “save messages from audio” and makes them **retrievable by API** (GET /transcripts) immediately. **Retrieval by radio** for live playout can be done by (1) polling GET /transcripts from a client that then triggers TX, or (2) a “play transcript over radio” endpoint (see below).

### 3.4 Optional: inject + store in one call

Alternatively (or in addition), extend `POST /inject/message` with a query or body flag `store=true`. When true:

- Require DB and transcript storage.
- Enforce whitelist on source/destination callsign.
- After pushing to injection queue, also call `TranscriptStorage.store(...)`. Return both `qsize` and `transcript_id`.

That way existing inject clients can opt into persistence without a new route; the “audio → store” route above then becomes “audio → ASR → inject + store” when you want both queue and DB.

### 3.5 Retrieval by API

- Keep `GET /transcripts` as is. Optionally: when `allowed_callsigns` is set, filter search results so that only transcripts whose `source_callsign` or `destination_callsign` is in the whitelist are returned (so the API never leaks “non-whitelisted” stored data). This is a policy choice.

### 3.6 Retrieval by radio

- **Polling**: A field client or script already can call `GET /transcripts?callsign=W1XYZ&band=2m` to get messages “for” that callsign. No change needed.
- **Play over radio**: To actually “play” a stored message on the air:
  - **Option A**: New endpoint `POST /transcripts/{id}/play` (or `POST /radio/play-message`) that: loads transcript by id, generates TTS with `text_to_speech_elevenlabs`, then invokes the same TX path as “approve pending” (radio_tx with audio file or use_tts). Requires access to radio_tx agent (e.g. from app state or orchestrator) and possibly a small “playback queue” so it’s serialized with other TX.
  - **Option B**: Client gets transcript text from `GET /transcripts`, then calls an existing “send message” endpoint that supports TTS (e.g. a generic “send this text over radio with TTS” route). If such a route exists, no backend change; otherwise add a thin route that builds a task for radio_tx (message + use_tts=True) and runs it.

So “retrievable by radio” is already there for **reading** (poll transcripts); “play over radio” needs one small path that connects transcript → TTS → radio_tx, either as a dedicated “play transcript” endpoint or a generic “send text via TTS” endpoint.

### 3.7 Where to implement (file-level)

| Change | File(s) |
|--------|--------|
| Whitelist config | `radioshaq/config/schema.py` (RadioConfig or new MessagesConfig) |
| Whitelist helper | New `radioshaq/api/whitelist.py` or in `relay.py`: `def is_callsign_allowed(callsign, config) -> bool` |
| Enforce in relay | `radioshaq/api/routes/relay.py`: after parsing callsigns, before `storage.store()` |
| New route audio→store | New `radioshaq/api/routes/messages.py` (or new file) + register in `server.py`: `POST /messages/from-audio` |
| Optional inject+store | `radioshaq/api/routes/inject.py`: if `store=true`, get storage + whitelist check + store |
| Optional GET /transcripts filter by whitelist | `radioshaq/api/routes/transcripts.py`: after `storage.search()`, filter by `allowed_callsigns` if set |
| Optional play-over-radio | New endpoint in `radio.py` or `transcripts.py` that loads transcript, runs TTS, calls radio_tx (needs agent from app state or tool registry) |

---

## 4. Summary

- **Whitelist**: Add `allowed_callsigns: list[str] | None` to config; enforce in relay and any new “store” route (reject 403 if callsign not allowed).
- **Save from audio**: Add `POST /messages/from-audio` (or similar) that: upload audio → ASR → whitelist check → `TranscriptStorage.store()`, and optionally inject to queue so radio_rx can see it too.
- **Existing routes**: Relay already saves; add whitelist check there. Inject currently does not save; optionally add “inject + store” with the same whitelist.
- **Retrieval by API**: `GET /transcripts` already; optionally filter results by whitelist.
- **Retrieval by radio**: Polling `GET /transcripts?callsign=...` already gives “messages for me”. To play a stored message over the air: add a small path that loads transcript → TTS → radio_tx (new endpoint or generic “send text with TTS” route).

All of this reuses existing infrastructure: ASR (`asr.py`), TTS (`tts.py`), `TranscriptStorage`, relay/transcripts routes, injection queue, and radio_tx with `use_tts`.
