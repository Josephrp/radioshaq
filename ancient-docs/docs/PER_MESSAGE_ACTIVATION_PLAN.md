# Per-message audio activation — investigation and implementation plan

This document describes the **current** session-level audio activation behaviour, the **proposed** per-message activation semantics, and a **complete implementation plan** (projects, activities, file-level tasks, line-level subtasks).

Reference: `radioshaq/radioshaq/specialized/radio_rx_audio.py` line 285 (comment: "Session-level: once activated, remains active until monitoring stops. Per-message activation could be added if needed.").

---

## 1. Current implementation (session-level activation)

### 1.1 Where it lives

| Location | What |
|----------|------|
| `radioshaq/radioshaq/specialized/radio_rx_audio.py` | Agent state `_audio_activated`, reset on monitor start/stop; check in `_on_segment_ready` |
| `radioshaq/radioshaq/config/schema.py` | `AudioConfig`: `audio_activation_enabled`, `audio_activation_phrase` |

### 1.2 Actual code flow

- **Line 186:** `self._audio_activated = False` in `__init__` (and effectively again when a new monitor task runs, because the same agent instance is used and `_action_monitor` sets `_monitoring = True` but does not reset `_audio_activated` until the `finally` block at line 250).
- **Lines 278–286:** In `_on_segment_ready`:
  - If `audio_activation_enabled` is False → skip activation block.
  - If `audio_activation_enabled` and **not** `_audio_activated`:
    - If transcript contains `audio_activation_phrase` → set `_audio_activated = True` and **continue** (process this segment and all following segments).
    - Else → `return` (drop this segment).
  - If already `_audio_activated` → do nothing (no re-check); segment is processed.
- **Line 250:** In `_action_monitor` finally block: `self._audio_activated = False` when monitoring stops.

So: one phrase match activates the **session**; every subsequent segment is processed until monitoring ends. There is no notion of “per message” or “per segment” today.

### 1.3 Message vs segment

- **Segment:** One unit emitted by `AudioStreamProcessor`: a VAD-delineated speech segment (one utterance from silence-to-silence). Each call to `_on_segment_ready(segment)` is one segment.
- **Message:** In this plan, “message” means one such segment that is **processed** (trigger filter passes and optionally a response is generated). So “per-message activation” means: **for each segment we consider for processing, we require the activation phrase to be present (or we require re-activation after each processed message).**

Two reasonable semantics:

- **Per-segment (strict):** Every segment must contain the activation phrase to be processed. No session-level memory.
- **Per-message (reset after process):** After we process one “message” (segment that passes trigger and is responded to or queued), we clear activation; the next segment again needs the phrase to be processed. So activation is required once per logical message/turn.

The plan below implements **configurable mode**: `session` (current) vs `per_message` (reset after each processed segment that passes trigger/response path).

---

## 2. Proposed behaviour: per-message activation

- **Session mode (current):** Once the activation phrase is heard, all subsequent segments in the session are processed until monitoring stops.
- **Per-message mode (new):** Each segment is only processed if it (or the “current turn”) contains the activation phrase; and after we process a segment (trigger passed, response generated or queued), we reset activation so the **next** segment again requires the phrase.

So in per-message mode:

1. Segment A: no phrase → dropped.
2. Segment B: contains phrase → processed (trigger check, response path); then set `_audio_activated = False`.
3. Segment C: no phrase → dropped.
4. Segment D: contains phrase → processed; then reset again.

Implementation detail: “reset after process” is done at the **end** of processing a segment (after trigger filter, and after we’ve either created pending, auto-responded, or returned for listen-only). So the reset happens once we’ve “consumed” the message.

---

## 3. Implementation plan (projects, activities, tasks, subtasks)

### Project 1: Config and schema

**Goal:** Add a configuration option to choose between session-level and per-message activation.

| Activity | File-level task | Line-level subtasks |
|----------|-----------------|----------------------|
| **1.1** Add activation mode enum and field | `radioshaq/radioshaq/config/schema.py` | (1) Define `AudioActivationMode` enum with values `session`, `per_message`. (2) Add `audio_activation_mode: AudioActivationMode = Field(default=AudioActivationMode.SESSION)` to `AudioConfig` (after `audio_activation_phrase`). (3) Export the enum in `__all__` if present. |
| **1.2** Backward compatibility | `radioshaq/radioshaq/config/schema.py` | (1) Default `audio_activation_mode` to `session` so existing configs behave unchanged. (2) If loading config from YAML/env, allow string `"session"` / `"per_message"` to map to enum. |

### Project 2: Agent logic (radio_rx_audio)

**Goal:** Implement per-message activation in the reception agent.

| Activity | File-level task | Line-level subtasks |
|----------|-----------------|----------------------|
| **2.1** Use activation mode in segment handler | `radioshaq/radioshaq/specialized/radio_rx_audio.py` | (1) Import `AudioActivationMode` from config schema. (2) In `_on_segment_ready`, after the existing activation block (lines 278–286), keep session behaviour when `config.audio_activation_mode == AudioActivationMode.SESSION`. (3) When `audio_activation_mode == AudioActivationMode.PER_MESSAGE`: if segment contains phrase, set `_audio_activated = True` for this segment only; do not set it for subsequent segments (treat as “activated for this segment”). (4) After processing a segment in per-message mode (after trigger filter and response path), set `_audio_activated = False` so the next segment requires the phrase again. |
| **2.2** Reset point for per-message | `radioshaq/radioshaq/specialized/radio_rx_audio.py` | (1) Identify the single exit path after “message processed” (after `_trigger_filter.check` and either `_confirmation_manager.create_pending`, `_send_response`, or listen-only return). (2) Add a helper or inline: at the end of “we processed this segment” (before any `return` that indicates “we handled this message”), if `audio_activation_mode == PER_MESSAGE`, set `self._audio_activated = False`. (3) Ensure we do not reset when we `return` early (e.g. SNR fail, no transcript, activation phrase missing, trigger filter fail). Only reset when we have actually processed the segment through trigger and response path. |

Concrete placement:

- **Lines 278–286:** Keep current logic but branch on mode:
  - **Session:** if not `_audio_activated` and phrase in transcript → set `_audio_activated = True`; else if not activated → `return`. Once activated, never clear until monitor stop.
  - **Per-message:** if phrase not in transcript → `return`. If phrase in transcript → treat as activated for this segment only (do not rely on persistent `_audio_activated` for “next” segment; instead reset at end of processing).
- **After line 301 (after `_send_response` in AUTO_RESPOND):** If per_message mode, set `_audio_activated = False`.
- **After line 296 (CONFIRM_FIRST create_pending):** If per_message mode, set `_audio_activated = False`.
- **After line 292 (LISTEN_ONLY return):** For listen_only we still “process” the message (trigger passed); if per_message, set `_audio_activated = False` before `return`.

So the flow becomes:

1. Activation check (session vs per-message):
   - Session: as now; per_message: require phrase in this transcript, else return.
2. Trigger filter check; if fail, return (no reset in per_message).
3. Generate response text.
4. If listen_only → [if per_message: set _audio_activated = False] return.
5. If confirm_first → create_pending; [if per_message: set _audio_activated = False] return.
6. If auto_respond → send_response; [if per_message: set _audio_activated = False] return.

### Project 3: API and UI

**Goal:** Expose activation mode and phrase in API and dashboard if desired.

| Activity | File-level task | Line-level subtasks |
|----------|-----------------|----------------------|
| **3.1** API | `radioshaq/radioshaq/api/routes/audio.py` | (1) No change required if `_audio_config_dict` uses `model_dump`; new field `audio_activation_mode` will be included automatically. (2) If PATCH validation is strict, allow `audio_activation_mode` in body and validate enum. |
| **3.2** Web types | `radioshaq/web-interface/src/types/audio.ts` | (1) Add `audio_activation_enabled?: boolean`, `audio_activation_phrase?: string`, `audio_activation_mode?: 'session' \| 'per_message'` to `AudioConfig` if not present. |
| **3.3** UI controls | `radioshaq/web-interface/src/features/audio/AudioConfigPage.tsx` | (1) Add section “Audio activation” with toggle for `audio_activation_enabled`, text input for phrase, and dropdown for `audio_activation_mode` (Session / Per-message). (2) Call `updateAudioConfig` on change. |

### Project 4: Tests

**Goal:** Unit tests for session vs per-message behaviour.

| Activity | File-level task | Line-level subtasks |
|----------|-----------------|----------------------|
| **4.1** Session mode unchanged | `radioshaq/tests/unit/specialized/test_radio_rx_audio.py` | (1) Test with `audio_activation_enabled=True`, `audio_activation_mode=session`: first segment without phrase dropped, segment with phrase processed, second segment without phrase still processed (mock segment callback or execute monitor with mocked stream_processor). (2) Use existing patterns (AsyncMock for capture_service, stream_processor). |
| **4.2** Per-message mode | `radioshaq/tests/unit/specialized/test_radio_rx_audio.py` | (1) Test: first segment with phrase processed; second segment without phrase dropped. (2) Test: segment with phrase processed, next segment with phrase processed again (both processed). (3) Test: segment without phrase dropped; segment with phrase processed; segment without phrase dropped. |
| **4.3** Config default | `radioshaq/tests/unit/config` or schema tests | (1) Ensure `AudioConfig()` has `audio_activation_mode == session`. (2) Ensure loading from dict with `audio_activation_mode: "per_message"` parses correctly. |

---

## 4. File-level summary

| File | Changes | Status |
|------|---------|--------|
| `radioshaq/radioshaq/config/schema.py` | Add `AudioActivationMode` enum; add `audio_activation_mode` to `AudioConfig`. | Done |
| `radioshaq/radioshaq/specialized/radio_rx_audio.py` | Branch activation on `audio_activation_mode`; in per_message mode require phrase per segment and set `_audio_activated = False` after each processed message. | Done |
| `radioshaq/radioshaq/api/routes/audio.py` | Optional: ensure PATCH accepts `audio_activation_mode`. (No change needed: `model_dump` and overlay `update(body)` include any key.) | Done |
| `radioshaq/web-interface/src/types/audio.ts` | Add `AudioActivationMode` enum and `audio_activation_enabled`, `audio_activation_phrase`, `audio_activation_mode` to `AudioConfig`. | Done |
| `radioshaq/web-interface/src/features/audio/AudioConfigPage.tsx` | Optional: add Audio activation section (toggle, phrase input, mode dropdown) and call `updateAudioConfig` on change. | Done |
| `radioshaq/tests/unit/specialized/test_radio_rx_audio.py` | Add tests for session (regression), per_message activation, config default, and dict load `"per_message"` parses. | Done |

---

## 5. Order of implementation

1. **Schema** — Add `AudioActivationMode` and `audio_activation_mode` (Project 1).
2. **Agent** — Implement per-message branch and reset in `_on_segment_ready` (Project 2).
3. **Tests** — Add unit tests (Project 4).
4. **API/UI** — Project 3.

---

## 6. Edge cases

- **Trigger filter fails:** Segment has phrase and we’re in per_message mode, but trigger filter fails. We should **not** reset activation (we didn’t “process” the message for response). So reset only when we pass trigger and enter response path (listen_only / create_pending / send_response).
- **ASR fails:** No transcript; we return early. No reset.
- **SNR too low:** Segment dropped before transcript. No reset.
- **Config without new field:** Default `session` preserves current behaviour.
