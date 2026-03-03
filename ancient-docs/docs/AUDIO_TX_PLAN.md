# Sending audio over the radio — plan and agent tool

This document describes the **issues** with the current voice TX path, **options** to send real audio via radio, and how to **wire everything as an agent tool** so the orchestrator (and optional LLM tools) can invoke “send audio over radio” correctly.

See also: [HARDWARE_CONNECTION.md](HARDWARE_CONNECTION.md) (rig wiring), [HACKRF_IMPLEMENTATION_PLAN.md](HACKRF_IMPLEMENTATION_PLAN.md) (SDR TX and compliance).

---

## 1. Current issues

| Issue | Where | What’s wrong |
|-------|--------|---------------|
| **No audio to rig** | `shakods/specialized/radio_tx.py` → `_transmit_voice()` | Only sets frequency, mode, keys PTT for 0.5 s, then unkeys. **No microphone, TTS, or file audio is sent to the transmitter.** |
| **REACT acting phase is placeholder** | `shakods/orchestrator/react_loop.py` → `_phase_acting()` | Marks tasks “completed” with `{"message": "Placeholder execution"}`. **Does not call `AgentRegistry.get_agent_for_task()` or `agent.execute(task)`.** |
| **No “send audio” agent tool** | ToolRegistry (nanobot) | No tool registered that an LLM (or API) can call to “send this message/audio over the radio.” TTS and relay exist but are not connected to TX. |

So today: voice TX is PTT-only; the orchestrator never runs real agent execution; there is no single invokable “send audio via radio” tool.

---

## 2. Options for sending audio over the radio

### Option A — CAT rig + sound card (IC-7300, FT-450D, etc.)

**Idea:** Audio is played from the PC to the rig’s **audio input** (e.g. “Line In” or “Data In” on the rig or its interface, e.g. SCU-17). PTT is controlled by the same code so the rig transmits only while audio is playing.

**Flow:**

1. **Audio source:**  
   - **Text:** `message` → TTS (e.g. ElevenLabs) → WAV/MP3 file or bytes.  
   - **File:** Caller provides `audio_path` (WAV/MP3).

2. **Playback:**  
   - Decode to PCM (e.g. 8–48 kHz, mono, matching rig expectations; many rigs expect 1.2–3 kHz for SSB).  
   - Play to a **specific sound device** (e.g. “Virtual Cable” or “Line Out” that is wired to the rig’s line in).  
   - Use a cross-platform playback library (e.g. `sounddevice`, `pyaudio`, or `miniaudio`) with configurable **output device** (name or index from config).

3. **PTT:**  
   - Key PTT **before** starting playback.  
   - Unkey PTT **after** playback ends (duration = audio length + optional short tail).

4. **Config:**  
   - `radio.audio_output_device`: optional; name or index of the sound device that feeds the rig. If unset, use system default (document that user must set default or this to the correct device).  
   - Optional: `radio.voice_use_tts`: if true and only `message` is given, call TTS before playing.

**Hardware:**  
- PC ↔ rig: CAT (Hamlib) for frequency, mode, PTT.  
- PC ↔ rig: audio cable (or virtual cable) from PC “audio out” to rig “line in” (or SCU-17 / similar).  
See [HARDWARE_CONNECTION.md](HARDWARE_CONNECTION.md).

---

### Option B — SDR TX (e.g. HackRF)

**Idea:** Generate I/Q from audio (e.g. SSB/FM modulation in software), send I/Q to the SDR; no separate “sound card to rig” cable.

**Flow:**

1. **Audio source:** Same as Option A (TTS or file).  
2. **Modulation:** Audio → baseband I/Q (e.g. SSB, FM, AM) at the chosen sample rate.  
3. **TX:** Send I/Q via the SDR TX path (e.g. `python_hackrf` callback or SoapySDR `writeStream`).  
4. **Compliance:** Same as [HACKRF_IMPLEMENTATION_PLAN.md](HACKRF_IMPLEMENTATION_PLAN.md): TX off by default, band allowlist, restricted-band blocklist, audit log, power/level limits.

Option B is independent of Option A: implement Option A first (CAT + sound) for existing rigs; add SDR TX later when HackRF (or other SDR) support is in place.

---

## 3. Agent tool: “send audio over radio”

### 3.1 What the tool does

- **Name:** e.g. `send_audio_over_radio` (or `transmit_voice` if we want to align with the existing capability name).  
- **Inputs:**  
  - `message` (string): Text to speak (if no `audio_path` and TTS is enabled).  
  - `frequency_hz` (number): Frequency in Hz.  
  - `mode` (string, optional): e.g. `"FM"`, `"LSB"`, `"USB"` (default from band or config).  
  - `audio_path` (string, optional): Path to WAV/MP3 file to send. If provided, this overrides TTS for the audio source.  
  - `use_tts` (boolean, optional): If true and only `message` is given, generate audio via TTS before TX.  
- **Behaviour:**  
  - If `audio_path` is set: use that file.  
  - Else if `message` and `use_tts`: call TTS → temp file (or bytes) → use that as audio.  
  - Else if `message` only: optional fallback to TTS from config, or return a clear error.  
  - Then: set frequency/mode (CAT or SDR), key PTT, play audio to the configured output (Option A) or modulate and send I/Q (Option B), unkey PTT.  
- **Output:** String or dict: success/failure, frequency, mode, duration, and any error message.

### 3.2 Where it lives

- **Specialized agent (existing):**  
  - `RadioTransmissionAgent` already has `execute(task)` and capabilities like `voice_transmission`.  
  - Extend `_transmit_voice(frequency_hz, message, mode, ...)` to accept optional `audio_path` and optional TTS; implement “play audio to device while PTT keyed” (Option A).  
  - Task payload: `transmission_type: "voice"`, `frequency`, `message`, `mode`, optional `audio_path`, optional `use_tts`.

- **Orchestrator:**  
  - In `react_loop.py`, **replace** the placeholder acting phase with: for each pending task, `agent = registry.get_agent_for_task(task)`, then if agent, `result = await agent.execute(task, upstream_callback)`; store `result` in the task and mark completed.  
  - So “send audio over radio” is executed when a decomposed task has the right type/capability and is handled by `RadioTransmissionAgent`.

- **LLM / ToolRegistry (nanobot):**  
  - Implement a **Tool** (protocol: `name`, `description`, `to_schema()`, `validate_params()`, `async execute(**kwargs) -> str`) that:  
    - Takes `message`, `frequency_hz`, `mode`, `audio_path`, `use_tts` as above.  
    - Calls the same logic as the agent (e.g. instantiate or get from app state: rig_manager + audio playback helper, run the same “set freq/mode → PTT on → play audio → PTT off” flow).  
  - Register this tool in the app’s `ToolRegistry` when the app creates it (e.g. in `server.py` or wherever the orchestrator/tools are initialised), so LLM function-calling can invoke “send audio over radio” by tool name.

### 3.3 Backend (CAT vs SDR)

- **CAT (Option A):** Tool and agent use `RigManager` (Hamlib) for frequency, mode, PTT, and an **audio playback helper** that plays a file/bytes to `config.radio.audio_output_device`.  
- **SDR (Option B):** When SDR TX is configured and the task requests it (or only SDR is available), use the SDR TX path (modulate + send I/Q) as in [HACKRF_IMPLEMENTATION_PLAN.md](HACKRF_IMPLEMENTATION_PLAN.md).  
- Document in the tool description and in this plan which backend is used (e.g. “Uses CAT rig + sound card when `radio.enabled`; SDR TX when `sdr_tx_enabled` and requested.”).

---

## 4. Implementation checklist

- [x] **Config:** Add `radio.audio_output_device` (optional str/int) and `radio.voice_use_tts` (bool).  
- [x] **Audio playback helper:** `shakods/audio/playback.py`: `play_audio_to_device(path=..., device=...)`; supports WAV/FLAC/OGG and MP3 (with pydub). Optional deps: `uv sync --extra voice_tx` (sounddevice, soundfile, pydub).  
- [x] **Radio TX agent:**  
  - [x] Extend `_transmit_voice()` to accept optional `audio_path` and `use_tts`; optional `config` in constructor for `audio_output_device` and `voice_use_tts`.  
  - [x] If audio (from file or TTS): key PTT, run playback in executor, unkey PTT.  
  - [x] If no audio: keep PTT 0.5 s “PTT only” behaviour.  
- [x] **Orchestrator:** `_phase_acting()` uses `agent_registry.get_agent_for_task(task_dict)` and `agent.execute(task_dict)`; `DecomposedTask` has optional `payload` for task params.  
- [x] **Agent tool (ToolRegistry):** `SendAudioOverRadioTool` in `shakods/specialized/radio_tools.py`; register when app has a ToolRegistry: `tool_registry.register(SendAudioOverRadioTool(rig_manager=..., config=...))`.  
- [ ] **Docs:** Update [HARDWARE_CONNECTION.md](HARDWARE_CONNECTION.md) with “Audio out to rig” (sound device, virtual cable, line-in).  
- [ ] **Tests:** Unit test for playback (mock device) and for agent `execute` with `audio_path` / `use_tts` (mock rig + mock playback).

---

## 5. Summary

| Goal | Approach |
|------|----------|
| **Send real audio via CAT rig** | Option A: TTS or file → decode → play to `audio_output_device` while PTT keyed; config for device. |
| **Send audio via SDR** | Option B: Modulate audio to I/Q, send via HackRF (or other SDR) path; see HACKRF_IMPLEMENTATION_PLAN. |
| **Orchestrator runs real tasks** | Wire `_phase_acting()` to `get_agent_for_task()` + `agent.execute()`. |
| **Agent tool for “send audio”** | Extend `RadioTransmissionAgent._transmit_voice()` for audio; add a Tool that reuses that logic and register it in ToolRegistry. |

This plan gives a clear path to send audio over the radio and expose it as a single agent tool (specialized agent + optional LLM tool).
