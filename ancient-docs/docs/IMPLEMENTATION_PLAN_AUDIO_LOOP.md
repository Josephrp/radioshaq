# SHAKODS Full Audio Loop — Implementation Plan

Complete implementation plan for **Listen to Radio → ASR → Agent → TTS → TX** with projects, activities, file-level tasks, and line-level subtasks. Uses **uv** for dependency management.

---

## Dependency setup (uv)

All work assumes the shakods package root. Run from `shakods/`:

```bash
cd shakods
uv sync --extra audio --extra voice_tx
```

Add the new optional group for voice RX (audio capture + VAD):

```bash
uv add --optional voice_rx sounddevice soundfile webrtcvad
```

never manually add to `pyproject.toml` 

---

## Project 1: Dependencies and configuration

**Goal:** Add optional dependency group `voice_rx` and extend config for audio capture/VAD/auto-response.

### Activity 1.1 — Optional dependency group `voice_rx`

use uv commands to produce this

### Activity 1.2 — Audio and radio config schema

| # | File-level task | Line-level subtasks |
|---|------------------|----------------------|
| 1.2.1 | **Edit** `shakods/shakods/config/schema.py` | After `RadioConfig` class (around line 199), define new model `AudioConfig(BaseModel)` with `model_config = ConfigDict(extra="ignore")`. |
| 1.2.2 | Same | In `AudioConfig`: add `input_device: str \| int \| None = Field(default=None, description="Audio input device (rig line-out)")`. |
| 1.2.3 | Same | Add `input_sample_rate: int = Field(default=16000)`. |
| 1.2.4 | Same | Add `vad_enabled: bool = Field(default=True)`. |
| 1.2.5 | Same | Add `vad_threshold: float = Field(default=0.02)`. |
| 1.2.6 | Same | Add `asr_model: str = Field(default="voxtral")`. |
| 1.2.7 | Same | Add `asr_language: str = Field(default="en")`. |
| 1.2.8 | Same | Add `auto_respond: bool = Field(default=False)`. |
| 1.2.9 | Same | Add `response_delay_ms: int = Field(default=500)`. |
| 1.2.10 | Same | Add `output_device: str \| int \| None = Field(default=None, description="Audio output device (rig line-in)")`. |
| 1.2.11 | **Edit** `shakods/shakods/config/schema.py` | In `RadioConfig`, add `audio_input_enabled: bool = Field(default=False)`. |
| 1.2.12 | Same | In `RadioConfig`, add `audio_output_enabled: bool = Field(default=False)`. |
| 1.2.13 | Same | In `Config` (around line 319), add `audio: AudioConfig = Field(default_factory=AudioConfig)`. |
| 1.2.14 | Same | In `__all__` (if present), add `"AudioConfig"`. |

---

## Project 2: Audio capture service (VAD + recording)

**Goal:** New module that captures from rig line-out, runs VAD, and invokes a callback with a temp WAV path when speech ends.

### Activity 2.1 — Create `shakods/audio/capture.py`

| # | File-level task | Line-level subtasks |
|---|------------------|----------------------|
| 2.1.1 | **Create** `shakods/shakods/audio/capture.py` | Add module docstring: "Audio capture from radio line-out with VAD triggering." |
| 2.1.2 | Same | Imports: `asyncio`, `tempfile`, `Path` from pathlib, `Callable`, `Awaitable` from typing, `numpy as np`, `logger` from loguru. |
| 2.1.3 | Same | Define class `AudioCaptureService` with `__init__(self, input_device=None, sample_rate=16000, chunk_duration_ms=100, vad_threshold=0.02, silence_duration_ms=1000, min_speech_duration_ms=500)`. |
| 2.1.4 | Same | In `__init__`: set `_chunk_samples = int(sample_rate * chunk_duration_ms / 1000)`, `_running = False`, `_audio_buffer: list[np.ndarray] = []`, `_speech_started`, `_silence_chunks`, `_max_silence_chunks`, `_min_speech_chunks`. |
| 2.1.5 | Same | Implement `async def start(self, on_speech_captured: Callable[[Path], Awaitable[None]]) -> None`: try/import `sounddevice as sd`, set `_running = True`. |
| 2.1.6 | Same | In `start`: define nested `audio_callback(indata, frames, time_info, status)` that computes RMS with `np.sqrt(np.mean(indata**2))`. |
| 2.1.7 | Same | In callback: if `rms > vad_threshold` and not `_speech_started`, set `_speech_started = True`, clear buffer, append `indata.copy()`; reset `_silence_chunks`. |
| 2.1.8 | Same | In callback: else if `_speech_started`, increment `_silence_chunks`; if &lt; max keep appending; else if buffer length ≥ min_speech_chunks, schedule `_process_captured_audio(on_speech_captured)` via `asyncio.create_task`, then reset state. |
| 2.1.9 | Same | In `start`: open `sd.InputStream(device=..., channels=1, samplerate=..., blocksize=_chunk_samples, dtype=np.float32, callback=audio_callback)` and loop `while _running: await asyncio.sleep(0.1)`. |
| 2.1.10 | Same | Implement `async def _process_captured_audio(self, callback)` that imports `soundfile as sf`, concatenates `_audio_buffer` with `np.concatenate`, writes to `tempfile.NamedTemporaryFile(suffix=".wav", delete=False)`, calls `await callback(temp_path)`, then `temp_path.unlink(missing_ok=True)`. |
| 2.1.11 | Same | Implement `def stop(self): self._running = False`. |
| 2.1.12 | Same | Add `RuntimeError` in `start` if `sounddevice` not installed, with message to run `uv sync --extra voice_rx`. |

### Activity 2.2 — Export capture from audio package

| # | File-level task | Line-level subtasks |
|---|------------------|----------------------|
| 2.2.1 | **Edit** `shakods/shakods/audio/__init__.py` | In `__getattr__`, add branch for `"AudioCaptureService"` returning `from shakods.audio.capture import AudioCaptureService`. |
| 2.2.2 | Same | Add `"AudioCaptureService"` to `__all__` if listing public names. |

---

## Project 3: Radio audio reception agent

**Goal:** New specialized agent that uses AudioCaptureService + ASR and can optionally trigger a response agent (TTS → TX).

### Activity 3.1 — Create `shakods/specialized/radio_rx_audio.py`

| # | File-level task | Line-level subtasks |
|---|------------------|----------------------|
| 3.1.1 | **Create** `shakods/shakods/specialized/radio_rx_audio.py` | Module docstring: "Radio reception agent with ASR integration for voice monitoring." |
| 3.1.2 | Same | Imports: `asyncio`, `Path` from pathlib, `Any` from typing, `logger` from loguru, `SpecializedAgent` from shakods.specialized.base. |
| 3.1.3 | Same | Define class `RadioAudioReceptionAgent(SpecializedAgent)` with `name = "radio_rx_audio"`, `description = "Monitors radio audio, transcribes speech, and processes messages"`, `capabilities = ["voice_monitoring", "speech_recognition", "audio_triggered_response"]`. |
| 3.1.4 | Same | `__init__(self, rig_manager=None, capture_service=None, asr_model="voxtral", auto_respond=False, response_agent=None)`, set `_monitoring = False`. |
| 3.1.5 | Same | Implement `async def execute(self, task, upstream_callback=None)`: read `action = task.get("action", "monitor")`. |
| 3.1.6 | Same | If `action == "monitor"`: extract `frequency`, `duration_seconds`, `mode`, return `await self.monitor_audio_frequency(...)`. |
| 3.1.7 | Same | Elif `action == "transcribe_file"`: `audio_path = task.get("audio_path")`, return `await self.transcribe_and_process(audio_path, upstream_callback)`. |
| 3.1.8 | Same | Else: return `{"error": f"Unknown action: {action}"}`. |
| 3.1.9 | Same | Implement `async def monitor_audio_frequency(self, frequency, duration_seconds, mode="FM", upstream_callback=None)`: if rig_manager, call `set_frequency` and `set_mode`. |
| 3.1.10 | Same | If not capture_service, return `{"error": "Audio capture service not configured", "frequency", "mode"}`. |
| 3.1.11 | Same | Set `_monitoring = True`, `transcripts = []`, define async `on_speech_captured(audio_path)` that calls `transcribe_and_process(str(audio_path), upstream_callback)`, appends to transcripts; if auto_respond and response_agent and result has transcript, call `_generate_response(...)`. |
| 3.1.12 | Same | `await asyncio.wait_for(capture_service.start(on_speech_captured), timeout=duration_seconds)` in try; except TimeoutError pass; finally `_monitoring = False`, `capture_service.stop()`. |
| 3.1.13 | Same | Return dict with `frequency`, `duration`, `mode`, `transcripts_captured`, `transcripts`. |
| 3.1.14 | Same | Implement `async def transcribe_and_process(self, audio_path, upstream_callback=None)`: emit progress "transcribing", then if asr_model == "voxtral" use `transcribe_audio_voxtral(audio_path, language="en")`, else fallback to whisper `model.transcribe(audio_path)`. |
| 3.1.15 | Same | Emit result with `type="transcription"`, `transcript`, `audio_path`; return `{"transcript", "audio_path", "model"}`; on exception emit_error and return `{"error": str(e), "audio_path"}`. |
| 3.1.16 | Same | Implement `async def _generate_response(self, incoming_message, frequency, mode, upstream_callback=None)`: emit progress "generating_response"; if response_agent, build task dict with transmission_type="voice", frequency, message (e.g. "Acknowledged: ..."), mode, use_tts=True; await response_agent.execute(response_task); emit result type "response_sent". |

### Activity 3.2 — Register agent in orchestrator registry

| # | File-level task | Line-level subtasks |
|---|------------------|----------------------|
| 3.2.1 | **Edit** `shakods/shakods/orchestrator/registry.py` (or factory) | Import `RadioAudioReceptionAgent`; ensure it is instantiated and registered when audio/capture is available (optional dependency). |
| 3.2.2 | If no registry pattern | In factory or wherever agents are built, add conditional: if voice_rx deps and config.radio.audio_input_enabled, create RadioAudioReceptionAgent and add to registry. |

---

## Project 4: Integration pipeline (audio → REACT → TTS → TX)

**Goal:** Wire capture → ASR → orchestrator (or direct agent) → TTS → playback/PTT so one command can run the full loop.

### Activity 4.1 — Optional: Audio-triggered pipeline helper

| # | File-level task | Line-level subtasks |
|---|------------------|----------------------|
| 4.1.1 | **Create** `shakods/shakods/audio/pipeline.py` (optional) | Define async function `run_audio_triggered_loop(capture_service, orchestrator_or_callback, tx_agent, config)` that starts capture with on_speech_captured doing: ASR → call orchestrator or callback with text → get reply text → TTS → tx_agent.execute(voice task). |
| 4.1.2 | Same | Use config for response_delay_ms, asr_language, etc. |

### Activity 4.2 — Wire upstream_callback in REACT for agents

| # | File-level task | Line-level subtasks |
|---|------------------|----------------------|
| 4.2.1 | **Edit** `shakods/shakods/orchestrator/react_loop.py` | In `_phase_acting`, build an upstream_callback that pushes UpstreamEvent into state.context (e.g. via MemoryUpstreamMiddleware or a simple list). |
| 4.2.2 | Same | Replace `agent.execute(task_dict, upstream_callback=None)` with `agent.execute(task_dict, upstream_callback=...)` when middleware or handler is available. |

---

## Project 5: Configuration and docs

**Goal:** Sample config and README so users can enable voice_rx and run the full loop.

### Activity 5.1 — Config sample and env

| # | File-level task | Line-level subtasks |
|---|------------------|----------------------|
| 5.1.1 | **Edit** `shakods/examples/config_sample.yaml` | Add section `audio:` with keys: `input_device`, `input_sample_rate`, `vad_enabled`, `vad_threshold`, `asr_model`, `asr_language`, `auto_respond`, `response_delay_ms`, `output_device`. |
| 5.1.2 | Same | Under `radio:` add `audio_input_enabled: false`, `audio_output_enabled: false`. |
| 5.1.3 | **Doc** | In README or docs, add: install with `uv sync --extra audio --extra voice_tx --extra voice_rx`; set `SHAKODS_RADIO__AUDIO_INPUT_ENABLED=1` and `SHAKODS_AUDIO__AUTO_RESPOND=0` (or 1) for testing. |

### Activity 5.2 — Usage example in plan or README

| # | File-level task | Line-level subtasks |
|---|------------------|----------------------|
| 5.2.1 | **Edit** `shakods/examples/README.md` or this plan | Add "Full audio loop" example: create AudioCaptureService, RadioAudioReceptionAgent with capture_service, asr_model, auto_respond=True, response_agent=RadioTransmissionAgent(...); call `rx_agent.execute({"action": "monitor", "frequency": 146520000, "duration_seconds": 300, "mode": "FM"})`. |

---

## Project 6: Tests

**Goal:** Unit tests for capture (mocked stream), for RadioAudioReceptionAgent (transcribe_file with temp file), and optional integration test with mocked capture.

### Activity 6.1 — Tests for AudioCaptureService

| # | File-level task | Line-level subtasks |
|---|------------------|----------------------|
| 6.1.1 | **Create** `shakods/tests/unit/audio/test_capture.py` | Pytest: skip if sounddevice/soundfile not installed (import check). |
| 6.1.2 | Same | Test that AudioCaptureService instantiates with default args. |
| 6.1.3 | Same | Test stop() sets _running = False. |
| 6.1.4 | Same | Optional: test _process_captured_audio with mock buffer and temp file callback. |

### Activity 6.2 — Tests for RadioAudioReceptionAgent

| # | File-level task | Line-level subtasks |
|---|------------------|----------------------|
| 6.2.1 | **Create** `shakods/tests/unit/specialized/test_radio_rx_audio.py` | Test execute with action "transcribe_file" and mock ASR returning fixed text; assert result has transcript, audio_path, model. |
| 6.2.2 | Same | Test execute with action "monitor" and no capture_service returns error dict. |
| 6.2.3 | Same | Test unknown action returns error dict. |

---

## Implementation checklist (summary)

| Component | Status | Project / Activity |
|-----------|--------|----------------------|
| voice_rx optional deps (sounddevice, soundfile, webrtcvad) | To do | Project 1.1 |
| AudioConfig + RadioConfig.audio_input/output_enabled | To do | Project 1.2 |
| AudioCaptureService (capture.py) | To do | Project 2.1–2.2 |
| RadioAudioReceptionAgent (radio_rx_audio.py) | To do | Project 3.1–3.2 |
| REACT upstream_callback wired to agents | To do | Project 4.2 |
| Optional pipeline helper | To do | Project 4.1 |
| Config sample + docs | To do | Project 5 |
| Unit tests (capture + rx_audio) | To do | Project 6 |

---

## uv commands reference

- From repo root (monorepo):  
  `cd shakods && uv sync --extra audio --extra voice_tx --extra voice_rx`
- Add optional group (if not in pyproject yet):  
  `uv add --optional voice_rx sounddevice soundfile webrtcvad`
- Run tests:  
  `uv run pytest shakods/tests/unit/audio shakods/tests/unit/specialized/test_radio_rx_audio.py -v`
- Run API with audio features:  
  `uv run python -m shakods.api.server` (after config/env set)

---

*Plan version: 1.0. Place this file in the shakods directory (.).*
