# SHAKODS Full Audio Loop — Improved Implementation Plan v2.0

Complete implementation plan for **Listen to Radio → Denoise → ASR → Agent → TTS → TX** with real-time stream processing, human-in-the-loop controls, and a modern web configuration interface.

**Key improvements over v1.0:**
- Real-time stream processing with denoising pipeline
- Response modes with human confirmation
- Trigger phrase/callsign filtering
- PTT coordination and half-duplex state machine
- WebRTC VAD with noise adaptation
- TypeScript/React configuration interface

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Dependencies (uv)](#2-dependencies-uv)
3. [Audio Stream Processing Pipeline](#3-audio-stream-processing-pipeline)
4. [Configuration Schema Extensions](#4-configuration-schema-extensions)
5. [Core Implementation](#5-core-implementation)
6. [Human-in-the-Loop Controls](#6-human-in-the-loop-controls)
7. [Web Configuration Interface (TypeScript/React)](#7-web-configuration-interface-typescriptreact)
8. [Integration & Orchestration](#8-integration--orchestration)
9. [Testing Strategy](#9-testing-strategy)
10. [Implementation Checklist](#10-implementation-checklist)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RADIO AUDIO PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐  │
│  │  Radio   │──▶│  AGC +   │──▶│ Denoise  │──▶│  VAD     │──▶│  ASR     │  │
│  │  RX In   │   │  Preproc │   │ (RNNoise)│   │ (WebRTC) │   │ (Voxtral)│  │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └────┬─────┘  │
│                                                                   │         │
│                              ┌────────────────────────────────────┘         │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    RadioAudioReceptionAgent                          │   │
│  │  ┌─────────────┐   ┌─────────────┐   ┌──────────────────────────┐   │   │
│  │  │  Trigger    │──▶│  Response   │──▶│  Response Queue/         │   │   │
│  │  │  Filter     │   │  Mode Logic │   │  Human Confirmation      │   │   │
│  │  └─────────────┘   └─────────────┘   └──────────────────────────┘   │   │
│  └────────────────────┬────────────────────────────────────────────────┘   │
│                       │                                                     │
│         ┌─────────────┼─────────────┐                                       │
│         ▼             ▼             ▼                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                                  │
│  │  Store   │  │  REACT   │  │  Direct  │                                  │
│  │  Transcript│  │  Orchestrator│  │  Auto-   │                                  │
│  │          │  │          │  │  Response│                                  │
│  └──────────┘  └────┬─────┘  └────┬─────┘                                  │
│                     │             │                                         │
│                     └─────────────┘                                         │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    RadioTransmissionAgent                            │   │
│  │  ┌─────────────┐   ┌─────────────┐   ┌──────────────────────────┐   │   │
│  │  │  PTT        │──▶│  TTS        │──▶│  TX Audio                │   │   │
│  │  │  Coordination│   │  (if needed)│   │  (PTT + Playback)        │   │   │
│  │  └─────────────┘   └─────────────┘   └──────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Dependencies (uv)

### 2.1 Add Optional Dependency Group `voice_rx`

```bash
# From shakods/ directory
uv add --optional voice_rx sounddevice soundfile webrtcvad-wheels numpy rnnoise-python

# Note: rnnoise-python may need system RNNoise library or custom build
# Alternative: use onnxruntime-based noise suppression
uv add --optional voice_rx onnxruntime-silence
```

### 2.2 Updated pyproject.toml Dependencies

```toml
[project.optional-dependencies]
# ... existing groups ...

# Voice RX: audio capture + preprocessing + VAD + ASR
voice_rx = [
    "sounddevice>=0.4.6",
    "soundfile>=0.12.1",
    "webrtcvad-wheels>=2.0.11",  # WebRTC VAD with wheels
    "numpy>=2.4",
    "rnnoise-python>=0.2",       # Or alternative denoising
    "noisereduce>=3.0",          # Spectral noise reduction fallback
]
```

---

## 3. Audio Stream Processing Pipeline

### 3.1 Stream Processing Architecture

```python
# shakods/shakods/audio/stream_processor.py

"""Real-time audio stream processor with denoising and VAD."""

from __future__ import annotations

import asyncio
import numpy as np
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Awaitable, Callable, Protocol

from loguru import logger


class StreamState(Enum):
    """States for the stream processor state machine."""
    IDLE = auto()
    NOISE_CALIBRATION = auto()
    LISTENING = auto()
    SPEECH_DETECTED = auto()
    SPEECH_ENDED = auto()
    PROCESSING = auto()
    CONFIRMATION_WAITING = auto()
    TRANSMITTING = auto()


@dataclass
class AudioFrame:
    """Single frame of audio with metadata."""
    samples: np.ndarray
    timestamp_ms: float
    sample_rate: int
    rms: float = 0.0
    is_speech: bool = False
    
    def __post_init__(self):
        if self.rms == 0.0 and len(self.samples) > 0:
            self.rms = np.sqrt(np.mean(self.samples.astype(np.float32) ** 2))


@dataclass
class ProcessedSegment:
    """Complete speech segment after VAD."""
    audio: np.ndarray
    sample_rate: int
    start_time_ms: float
    end_time_ms: float
    duration_ms: float
    avg_rms: float
    snr_db: float | None = None
    
    # Will be populated by ASR
    transcript: str | None = None
    transcript_confidence: float | None = None


class AudioPreprocessor:
    """Audio preprocessing: AGC, high-pass filter, normalization."""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        agc_target_rms: float = 0.1,
        agc_max_gain: float = 10.0,
        highpass_cutoff: float = 80.0,
    ):
        self.sample_rate = sample_rate
        self.agc_target_rms = agc_target_rms
        self.agc_max_gain = agc_max_gain
        self.highpass_cutoff = highpass_cutoff
        self._agc_gain = 1.0
        self._hp_state = np.zeros(2)  # High-pass filter state
        
    def process(self, frame: np.ndarray) -> np.ndarray:
        """Apply preprocessing chain to audio frame."""
        # 1. High-pass filter to remove low-frequency noise
        frame = self._highpass_filter(frame)
        
        # 2. AGC (Automatic Gain Control)
        frame = self._apply_agc(frame)
        
        # 3. Normalize to prevent clipping
        max_val = np.max(np.abs(frame))
        if max_val > 0.99:
            frame = frame * (0.99 / max_val)
            
        return frame
    
    def _highpass_filter(self, samples: np.ndarray) -> np.ndarray:
        """Simple high-pass filter (remove rumble, hum)."""
        # RC filter approximation
        rc = 1.0 / (2 * np.pi * self.highpass_cutoff)
        alpha = rc / (rc + 1.0 / self.sample_rate)
        
        output = np.zeros_like(samples, dtype=np.float32)
        output[0] = samples[0] - self._hp_state[0]
        for i in range(1, len(samples)):
            output[i] = alpha * (output[i-1] + samples[i] - samples[i-1])
        
        self._hp_state[0] = samples[-1]
        return output
    
    def _apply_agc(self, samples: np.ndarray) -> np.ndarray:
        """Adaptive gain control."""
        rms = np.sqrt(np.mean(samples.astype(np.float64) ** 2))
        if rms > 0:
            target_gain = self.agc_target_rms / rms
            target_gain = min(target_gain, self.agc_max_gain)
            # Smooth gain adaptation
            self._agc_gain = 0.9 * self._agc_gain + 0.1 * target_gain
        return samples * self._agc_gain


class NoiseSuppressor:
    """Noise suppression using RNNoise or spectral subtraction."""
    
    def __init__(self, sample_rate: int = 16000, use_rnnoise: bool = True):
        self.sample_rate = sample_rate
        self.use_rnnoise = use_rnnoise
        self._rnnoise = None
        self._noise_profile: deque[np.ndarray] = deque(maxlen=50)  # ~5 sec at 100ms chunks
        
        if use_rnnoise:
            try:
                import rnnoise
                self._rnnoise = rnnoise.RNNoise()
                logger.info("RNNoise initialized for denoising")
            except ImportError:
                logger.warning("RNNoise not available, falling back to spectral subtraction")
                self.use_rnnoise = False
    
    def calibrate_noise(self, frame: np.ndarray) -> None:
        """Capture noise profile during silence."""
        self._noise_profile.append(frame.copy())
    
    def process(self, frame: np.ndarray) -> tuple[np.ndarray, float]:
        """Apply noise suppression, return (processed_frame, snr_estimate)."""
        if self.use_rnnoise and self._rnnoise:
            return self._rnnoise.process_frame(frame)
        else:
            return self._spectral_subtraction(frame)
    
    def _spectral_subtraction(self, frame: np.ndarray) -> tuple[np.ndarray, float]:
        """Fallback spectral subtraction denoising."""
        try:
            import noisereduce as nr
            if len(self._noise_profile) >= 10:
                noise_clip = np.concatenate(list(self._noise_profile))
                reduced = nr.reduce_noise(
                    y=frame,
                    y_noise=noise_clip,
                    sr=self.sample_rate,
                    prop_decrease=0.75,
                )
                snr = 10 * np.log10(np.var(frame) / (np.var(frame - reduced) + 1e-10))
                return reduced, snr
        except ImportError:
            pass
        return frame, 0.0


class WebRTCVAD:
    """WebRTC Voice Activity Detection wrapper."""
    
    def __init__(self, sample_rate: int = 16000, aggressiveness: int = 2):
        """
        Args:
            aggressiveness: 0-3, higher = more aggressive filtering
        """
        import webrtcvad
        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = sample_rate
        self.frame_duration_ms = 30  # WebRTC supports 10, 20, or 30ms
        self.frame_samples = int(sample_rate * self.frame_duration_ms / 1000)
        
    def is_speech(self, frame: np.ndarray) -> bool:
        """Check if frame contains speech."""
        # WebRTC requires specific frame sizes
        if len(frame) != self.frame_samples:
            return False
        
        # Convert to 16-bit PCM bytes
        pcm_bytes = (frame * 32767).astype(np.int16).tobytes()
        
        try:
            return self.vad.is_speech(pcm_bytes, self.sample_rate)
        except Exception:
            return False
    
    def process_stream(self, frames: list[np.ndarray]) -> list[bool]:
        """Process multiple frames."""
        return [self.is_speech(f) for f in frames]


class AudioStreamProcessor:
    """
    Real-time audio stream processor coordinating preprocessing, denoising, and VAD.
    
    Outputs complete speech segments ready for ASR.
    """
    
    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        vad_aggressiveness: int = 2,
        pre_speech_buffer_ms: int = 300,
        post_speech_buffer_ms: int = 400,
        min_speech_duration_ms: int = 500,
        max_speech_duration_ms: int = 30000,
        silence_duration_ms: int = 800,
        use_rnnoise: bool = True,
    ):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_samples = int(sample_rate * frame_duration_ms / 1000)
        
        # Buffers (in frames)
        self.pre_speech_frames = int(pre_speech_buffer_ms / frame_duration_ms)
        self.post_speech_frames = int(post_speech_buffer_ms / frame_duration_ms)
        self.min_speech_frames = int(min_speech_duration_ms / frame_duration_ms)
        self.max_speech_frames = int(max_speech_duration_ms / frame_duration_ms)
        self.silence_frames = int(silence_duration_ms / frame_duration_ms)
        
        # Components
        self.preprocessor = AudioPreprocessor(sample_rate=sample_rate)
        self.denoiser = NoiseSuppressor(sample_rate=sample_rate, use_rnnoise=use_rnnoise)
        self.vad = WebRTCVAD(sample_rate=sample_rate, aggressiveness=vad_aggressiveness)
        
        # State
        self._state = StreamState.IDLE
        self._ring_buffer: deque[np.ndarray] = deque(maxlen=self.pre_speech_frames)
        self._speech_buffer: list[np.ndarray] = []
        self._speech_frames = 0
        self._silence_frames = 0
        self._noise_calibration_active = True
        
        # Callbacks
        self._on_segment_ready: Callable[[ProcessedSegment], Awaitable[None]] | None = None
        
    def set_segment_callback(
        self,
        callback: Callable[[ProcessedSegment], Awaitable[None]]
    ) -> None:
        """Set callback for when a speech segment is ready."""
        self._on_segment_ready = callback
    
    async def process_frame(self, raw_frame: np.ndarray) -> None:
        """Process a single audio frame through the pipeline."""
        # 1. Preprocessing (AGC, high-pass)
        frame = self.preprocessor.process(raw_frame)
        
        # 2. Noise calibration (first few seconds)
        if self._noise_calibration_active:
            self.denoiser.calibrate_noise(frame)
            if len(self.denoiser._noise_profile) >= self.denoiser._noise_profile.maxlen:
                self._noise_calibration_active = False
                self._state = StreamState.LISTENING
                logger.info("Noise calibration complete")
            return
        
        # 3. Denoising
        denoised_frame, snr = self.denoiser.process(frame)
        
        # 4. VAD
        is_speech = self.vad.is_speech(denoised_frame)
        
        # 5. State machine for speech segmentation
        await self._update_state(is_speech, denoised_frame, snr)
    
    async def _update_state(
        self,
        is_speech: bool,
        frame: np.ndarray,
        snr: float
    ) -> None:
        """Update state machine based on VAD result."""
        
        if self._state == StreamState.LISTENING:
            if is_speech:
                self._state = StreamState.SPEECH_DETECTED
                self._speech_buffer = list(self._ring_buffer) + [frame]
                self._speech_frames = 1
                self._silence_frames = 0
                self._ring_buffer.clear()
            else:
                self._ring_buffer.append(frame)
                
        elif self._state == StreamState.SPEECH_DETECTED:
            self._speech_buffer.append(frame)
            
            if is_speech:
                self._speech_frames += 1
                self._silence_frames = 0
                
                # Check max duration
                if self._speech_frames >= self.max_speech_frames:
                    await self._finalize_segment(snr)
            else:
                self._silence_frames += 1
                
                # Check if speech ended
                if self._silence_frames >= self.silence_frames:
                    await self._finalize_segment(snr)
                elif self._silence_frames <= self.post_speech_frames:
                    # Still in post-speech buffer zone
                    self._speech_buffer.append(frame)
    
    async def _finalize_segment(self, snr: float) -> None:
        """Finalize current speech segment and emit."""
        if len(self._speech_buffer) >= self.min_speech_frames:
            audio = np.concatenate(self._speech_buffer)
            duration_ms = len(audio) / self.sample_rate * 1000
            
            segment = ProcessedSegment(
                audio=audio,
                sample_rate=self.sample_rate,
                start_time_ms=0,  # Relative to segment
                end_time_ms=duration_ms,
                duration_ms=duration_ms,
                avg_rms=float(np.sqrt(np.mean(audio ** 2))),
                snr_db=snr,
            )
            
            if self._on_segment_ready:
                await self._on_segment_ready(segment)
        
        # Reset state
        self._speech_buffer = []
        self._speech_frames = 0
        self._silence_frames = 0
        self._state = StreamState.LISTENING
    
    def reset(self) -> None:
        """Reset processor state."""
        self._state = StreamState.IDLE
        self._ring_buffer.clear()
        self._speech_buffer = []
        self._speech_frames = 0
        self._silence_frames = 0
        self._noise_calibration_active = True
```

### 3.2 Capture Service (Updated)

```python
# shakods/shakods/audio/capture.py

"""Audio capture service with stream processing integration."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol

import numpy as np
from loguru import logger

from shakods.audio.stream_processor import AudioStreamProcessor, ProcessedSegment


class AudioCaptureService:
    """
    Audio capture service that feeds into the stream processor.
    """
    
    def __init__(
        self,
        stream_processor: AudioStreamProcessor,
        input_device: str | int | None = None,
        sample_rate: int = 16000,
        chunk_duration_ms: int = 30,
    ):
        self.stream_processor = stream_processor
        self.input_device = input_device
        self.sample_rate = sample_rate
        self.chunk_samples = int(sample_rate * chunk_duration_ms / 1000)
        
        self._running = False
        self._stream = None
        self._capture_task: asyncio.Task | None = None
        
    async def start(self) -> None:
        """Start audio capture."""
        try:
            import sounddevice as sd
        except ImportError as e:
            raise RuntimeError(
                "sounddevice not installed. Run: uv sync --extra voice_rx"
            ) from e
        
        self._running = True
        
        def audio_callback(indata, frames, time_info, status):
            """Sounddevice callback (runs in separate thread)."""
            if status:
                logger.warning(f"Audio callback status: {status}")
            
            # Put frame into asyncio queue for processing
            frame = indata[:, 0].copy()  # Mono
            try:
                self._frame_queue.put_nowait(frame)
            except asyncio.QueueFull:
                pass
        
        self._frame_queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=100)
        
        self._stream = sd.InputStream(
            device=self.input_device,
            channels=1,
            samplerate=self.sample_rate,
            blocksize=self.chunk_samples,
            dtype=np.float32,
            callback=audio_callback,
        )
        
        self._stream.start()
        self._capture_task = asyncio.create_task(self._process_loop())
        logger.info(f"Audio capture started on device {self.input_device}")
    
    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                frame = await asyncio.wait_for(
                    self._frame_queue.get(),
                    timeout=1.0
                )
                await self.stream_processor.process_frame(frame)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.exception(f"Frame processing error: {e}")
    
    def stop(self) -> None:
        """Stop audio capture."""
        self._running = False
        if self._capture_task:
            self._capture_task.cancel()
        if self._stream:
            self._stream.stop()
            self._stream.close()
        logger.info("Audio capture stopped")
```

---

## 4. Configuration Schema Extensions

### 4.1 Enhanced Audio Configuration

```python
# shakods/shakods/config/schema.py (additions)

from enum import StrEnum


class ResponseMode(StrEnum):
    """Response modes for radio audio reception."""
    LISTEN_ONLY = "listen_only"          # Transcribe only, no TX
    CONFIRM_FIRST = "confirm_first"      # Queue for human approval
    AUTO_RESPOND = "auto_respond"        # Full auto (use with caution)
    CONFIRM_TIMEOUT = "confirm_timeout"  # Auto-respond after timeout if not rejected


class VADMode(StrEnum):
    """WebRTC VAD aggressiveness presets."""
    NORMAL = "normal"      # Aggressiveness 0
    LOW_BITRATE = "low"    # Aggressiveness 1
    AGGRESSIVE = "aggressive"  # Aggressiveness 2
    VERY_AGGRESSIVE = "very_aggressive"  # Aggressiveness 3


class TriggerMatchMode(StrEnum):
    """How trigger phrases are matched."""
    EXACT = "exact"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    FUZZY = "fuzzy"  # Requires fuzzywuzzy or similar


class AudioConfig(BaseModel):
    """Audio processing configuration."""
    
    model_config = ConfigDict(extra="ignore")
    
    # Input/Output devices
    input_device: str | int | None = Field(
        default=None,
        description="Audio input device (radio line-out)"
    )
    input_sample_rate: int = Field(default=16000)
    output_device: str | int | None = Field(
        default=None,
        description="Audio output device (radio line-in)"
    )
    
    # Preprocessing
    preprocessing_enabled: bool = Field(default=True)
    agc_enabled: bool = Field(default=True)
    agc_target_rms: float = Field(default=0.1, ge=0.01, le=1.0)
    highpass_filter_enabled: bool = Field(default=True)
    highpass_cutoff_hz: float = Field(default=80.0, ge=20.0, le=500.0)
    
    # Denoising
    denoising_enabled: bool = Field(default=True)
    denoising_backend: str = Field(default="rnnoise")  # "rnnoise", "spectral", "none"
    noise_calibration_seconds: float = Field(default=3.0, ge=1.0, le=10.0)
    min_snr_db: float = Field(default=3.0, ge=-10.0, le=40.0)
    
    # VAD
    vad_enabled: bool = Field(default=True)
    vad_mode: VADMode = Field(default=VADMode.AGGRESSIVE)
    pre_speech_buffer_ms: int = Field(default=300, ge=0, le=1000)
    post_speech_buffer_ms: int = Field(default=400, ge=0, le=1000)
    min_speech_duration_ms: int = Field(default=500, ge=100, le=2000)
    max_speech_duration_ms: int = Field(default=30000, ge=5000, le=60000)
    silence_duration_ms: int = Field(default=800, ge=200, le=2000)
    
    # ASR
    asr_model: str = Field(default="voxtral")
    asr_language: str = Field(default="en")
    asr_min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    
    # Response behavior
    response_mode: ResponseMode = Field(default=ResponseMode.LISTEN_ONLY)
    response_timeout_seconds: float = Field(default=30.0, ge=5.0, le=120.0)
    response_delay_ms: int = Field(default=500, ge=0, le=5000)
    response_cooldown_seconds: float = Field(default=5.0, ge=1.0, le=60.0)
    
    # Trigger filtering
    trigger_enabled: bool = Field(default=True)
    trigger_phrases: list[str] = Field(default_factory=lambda: ["shakods", "field station"])
    trigger_match_mode: TriggerMatchMode = Field(default=TriggerMatchMode.CONTAINS)
    trigger_callsign: str | None = Field(default=None)
    trigger_min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    
    # PTT coordination
    ptt_coordination_enabled: bool = Field(default=True)
    ptt_cooldown_ms: int = Field(default=500, ge=100, le=2000)
    break_in_enabled: bool = Field(default=True)  # Allow operator to override


class RadioConfig(BaseModel):
    """Existing RadioConfig additions."""
    
    # ... existing fields ...
    
    audio_input_enabled: bool = Field(default=False)
    audio_output_enabled: bool = Field(default=False)
    audio_monitoring_enabled: bool = Field(default=False)  # Pass-through to operator
```

### 4.2 Confirmation Queue Model

```python
# shakods/shakods/config/schema.py (additions)

from datetime import datetime
from enum import StrEnum


class PendingResponseStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    AUTO_SENT = "auto_sent"


class PendingResponse(BaseModel):
    """A pending response awaiting human confirmation."""
    
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    
    # Source
    incoming_transcript: str
    incoming_audio_path: str | None = None
    frequency_hz: float | None = None
    mode: str | None = None
    
    # Proposed response
    proposed_message: str
    proposed_audio_path: str | None = None
    
    # Status
    status: PendingResponseStatus = PendingResponseStatus.PENDING
    responded_at: datetime | None = None
    responded_by: str | None = None  # Operator identifier
    notes: str | None = None
```

---

## 5. Core Implementation

### 5.1 Radio Audio Reception Agent (Enhanced)

```python
# shakods/shakods/specialized/radio_rx_audio.py

"""Radio reception agent with ASR and human-in-the-loop controls."""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from loguru import logger

from shakods.audio.stream_processor import ProcessedSegment, AudioStreamProcessor
from shakods.config.schema import (
    AudioConfig,
    PendingResponse,
    PendingResponseStatus,
    ResponseMode,
    TriggerMatchMode,
)
from shakods.middleware.upstream import UpstreamEvent
from shakods.specialized.base import SpecializedAgent


class TriggerFilter:
    """Filters transcripts based on trigger phrases and callsign."""
    
    def __init__(self, config: AudioConfig):
        self.config = config
        
    def check(self, transcript: str, confidence: float) -> bool:
        """
        Check if transcript passes trigger filters.
        
        Returns True if the message should be processed.
        """
        if not self.config.trigger_enabled:
            return True
        
        if confidence < self.config.trigger_min_confidence:
            logger.debug(f"Trigger rejected: confidence {confidence} < {self.config.trigger_min_confidence}")
            return False
        
        transcript_lower = transcript.lower()
        
        # Check callsign if configured
        if self.config.trigger_callsign:
            if self.config.trigger_callsign.lower() not in transcript_lower:
                logger.debug(f"Trigger rejected: callsign not found")
                return False
        
        # Check trigger phrases
        if not self.config.trigger_phrases:
            return True
        
        for phrase in self.config.trigger_phrases:
            phrase_lower = phrase.lower()
            
            match self.config.trigger_match_mode:
                case TriggerMatchMode.EXACT:
                    if phrase_lower == transcript_lower:
                        return True
                case TriggerMatchMode.CONTAINS:
                    if phrase_lower in transcript_lower:
                        return True
                case TriggerMatchMode.STARTS_WITH:
                    if transcript_lower.startswith(phrase_lower):
                        return True
                case TriggerMatchMode.FUZZY:
                    # Requires fuzzy matching library
                    try:
                        from rapidfuzz import fuzz
                        score = fuzz.partial_ratio(phrase_lower, transcript_lower)
                        if score >= 80:  # Configurable threshold
                            return True
                    except ImportError:
                        pass
        
        logger.debug(f"Trigger rejected: no matching phrase")
        return False


class ConfirmationManager:
    """Manages pending responses awaiting human confirmation."""
    
    def __init__(self, config: AudioConfig):
        self.config = config
        self._pending: dict[str, PendingResponse] = {}
        self._callbacks: list[Callable[[PendingResponse], Awaitable[None]]] = []
        self._lock = asyncio.Lock()
        
    def add_callback(
        self,
        callback: Callable[[PendingResponse], Awaitable[None]]
    ) -> None:
        """Add callback for status changes."""
        self._callbacks.append(callback)
    
    async def create_pending(
        self,
        transcript: str,
        proposed_message: str,
        frequency_hz: float | None = None,
        mode: str | None = None,
        incoming_audio_path: str | None = None,
    ) -> PendingResponse:
        """Create a new pending response."""
        expires = datetime.utcnow() + timedelta(
            seconds=self.config.response_timeout_seconds
        )
        
        pending = PendingResponse(
            expires_at=expires,
            incoming_transcript=transcript,
            proposed_message=proposed_message,
            frequency_hz=frequency_hz,
            mode=mode,
            incoming_audio_path=incoming_audio_path,
        )
        
        async with self._lock:
            self._pending[pending.id] = pending
        
        await self._notify_change(pending)
        return pending
    
    async def approve(self, pending_id: str, operator: str | None = None) -> PendingResponse | None:
        """Approve a pending response."""
        async with self._lock:
            if pending_id not in self._pending:
                return None
            
            pending = self._pending[pending_id]
            pending.status = PendingResponseStatus.APPROVED
            pending.responded_at = datetime.utcnow()
            pending.responded_by = operator
            
        await self._notify_change(pending)
        return pending
    
    async def reject(self, pending_id: str, operator: str | None = None, notes: str | None = None) -> PendingResponse | None:
        """Reject a pending response."""
        async with self._lock:
            if pending_id not in self._pending:
                return None
            
            pending = self._pending[pending_id]
            pending.status = PendingResponseStatus.REJECTED
            pending.responded_at = datetime.utcnow()
            pending.responded_by = operator
            pending.notes = notes
            
        await self._notify_change(pending)
        return pending
    
    async def get_pending(self, pending_id: str) -> PendingResponse | None:
        """Get a pending response by ID."""
        async with self._lock:
            return self._pending.get(pending_id)
    
    async def list_pending(self) -> list[PendingResponse]:
        """List all pending responses."""
        async with self._lock:
            # Clean expired
            now = datetime.utcnow()
            expired = [
                id for id, p in self._pending.items()
                if p.expires_at < now and p.status == PendingResponseStatus.PENDING
            ]
            for id in expired:
                self._pending[id].status = PendingResponseStatus.EXPIRED
            
            return [
                p for p in self._pending.values()
                if p.status == PendingResponseStatus.PENDING
            ]
    
    async def _notify_change(self, pending: PendingResponse) -> None:
        """Notify all callbacks of status change."""
        for callback in self._callbacks:
            try:
                await callback(pending)
            except Exception as e:
                logger.exception(f"Confirmation callback error: {e}")


class RadioAudioReceptionAgent(SpecializedAgent):
    """
    Radio reception agent with ASR integration, trigger filtering,
    and human-in-the-loop confirmation.
    """
    
    name = "radio_rx_audio"
    description = "Monitors radio audio with ASR, triggers, and human confirmation"
    capabilities = [
        "voice_monitoring",
        "speech_recognition",
        "audio_triggered_response",
        "human_in_the_loop",
    ]
    
    def __init__(
        self,
        config: AudioConfig,
        rig_manager: Any | None = None,
        capture_service: Any | None = None,
        stream_processor: AudioStreamProcessor | None = None,
        response_agent: Any | None = None,
    ):
        self.config = config
        self.rig_manager = rig_manager
        self.capture_service = capture_service
        self.stream_processor = stream_processor
        self.response_agent = response_agent
        
        self._monitoring = False
        self._trigger_filter = TriggerFilter(config)
        self._confirmation_manager = ConfirmationManager(config)
        self._last_response_time: datetime | None = None
        self._cooldown_lock = asyncio.Lock()
        
        # Wire up stream processor callback
        if self.stream_processor:
            self.stream_processor.set_segment_callback(self._on_segment_ready)
        
        # Start confirmation timeout watcher
        self._confirmation_task: asyncio.Task | None = None
    
    async def execute(
        self,
        task: dict[str, Any],
        upstream_callback: Callable[[UpstreamEvent], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """Execute audio monitoring task."""
        action = task.get("action", "monitor")
        
        if action == "monitor":
            return await self._action_monitor(task, upstream_callback)
        elif action == "transcribe_file":
            return await self._action_transcribe_file(task, upstream_callback)
        elif action == "approve_response":
            return await self._action_approve_response(task)
        elif action == "reject_response":
            return await self._action_reject_response(task)
        elif action == "list_pending":
            return await self._action_list_pending()
        elif action == "get_pending":
            return await self._action_get_pending(task)
        else:
            return {"error": f"Unknown action: {action}"}
    
    async def _action_monitor(
        self,
        task: dict[str, Any],
        upstream_callback: Callable[[UpstreamEvent], Awaitable[None]] | None,
    ) -> dict[str, Any]:
        """Start monitoring audio frequency."""
        frequency = task.get("frequency")
        duration_seconds = task.get("duration_seconds", 300)
        mode = task.get("mode", "FM")
        
        if not self.capture_service or not self.stream_processor:
            return {"error": "Audio capture not configured"}
        
        # Set radio frequency if rig manager available
        if self.rig_manager and frequency:
            await self.rig_manager.set_frequency(frequency)
            await self.rig_manager.set_mode(mode)
        
        self._monitoring = True
        transcripts = []
        
        # Start confirmation watcher
        self._confirmation_task = asyncio.create_task(
            self._confirmation_watcher(upstream_callback)
        )
        
        await self.emit_progress(upstream_callback, "monitoring_started", 
                                 frequency=frequency, mode=mode)
        
        try:
            await asyncio.wait_for(
                self.capture_service.start(),
                timeout=duration_seconds
            )
        except asyncio.TimeoutError:
            pass
        finally:
            self._monitoring = False
            self.capture_service.stop()
            if self._confirmation_task:
                self._confirmation_task.cancel()
        
        return {
            "frequency": frequency,
            "duration": duration_seconds,
            "mode": mode,
            "transcripts_captured": len(transcripts),
        }
    
    async def _on_segment_ready(self, segment: ProcessedSegment) -> None:
        """Handle processed speech segment from stream processor."""
        if not self._monitoring:
            return
        
        # Check SNR
        if segment.snr_db is not None and segment.snr_db < self.config.min_snr_db:
            logger.debug(f"Segment rejected: SNR {segment.snr_db} < {self.config.min_snr_db}")
            return
        
        # ASR
        transcript = await self._transcribe_segment(segment)
        if not transcript:
            return
        
        segment.transcript = transcript
        
        # Check cooldown
        if not await self._check_cooldown():
            logger.debug("Response in cooldown period")
            return
        
        # Trigger filter
        confidence = segment.transcript_confidence or 0.8
        if not self._trigger_filter.check(transcript, confidence):
            # Still emit as transcription but don't trigger response
            await self.emit_result(None, {
                "type": "transcription_filtered",
                "transcript": transcript,
                "reason": "trigger_mismatch",
            })
            return
        
        # Generate response
        response_text = await self._generate_response_text(transcript)
        
        # Handle based on response mode
        match self.config.response_mode:
            case ResponseMode.LISTEN_ONLY:
                await self.emit_result(None, {
                    "type": "transcription",
                    "transcript": transcript,
                    "response": response_text,
                    "action": "none (listen_only mode)",
                })
            
            case ResponseMode.CONFIRM_FIRST:
                pending = await self._confirmation_manager.create_pending(
                    transcript=transcript,
                    proposed_message=response_text,
                )
                await self.emit_result(None, {
                    "type": "awaiting_confirmation",
                    "pending_id": pending.id,
                    "transcript": transcript,
                    "proposed_response": response_text,
                    "expires_at": pending.expires_at.isoformat(),
                })
            
            case ResponseMode.CONFIRM_TIMEOUT:
                pending = await self._confirmation_manager.create_pending(
                    transcript=transcript,
                    proposed_message=response_text,
                )
                # Auto-send after timeout
                asyncio.create_task(self._auto_send_after_timeout(pending.id))
                await self.emit_result(None, {
                    "type": "awaiting_confirmation_auto",
                    "pending_id": pending.id,
                    "transcript": transcript,
                    "proposed_response": response_text,
                    "expires_at": pending.expires_at.isoformat(),
                })
            
            case ResponseMode.AUTO_RESPOND:
                await self._send_response(response_text)
                await self.emit_result(None, {
                    "type": "auto_response_sent",
                    "transcript": transcript,
                    "response": response_text,
                })
    
    async def _confirmation_watcher(
        self,
        upstream_callback: Callable[[UpstreamEvent], Awaitable[None]] | None
    ) -> None:
        """Watch for approved confirmations and send responses."""
        async def on_change(pending: PendingResponse):
            if pending.status == PendingResponseStatus.APPROVED:
                await self._send_response(pending.proposed_message)
                await self.emit_result(upstream_callback, {
                    "type": "response_sent_confirmed",
                    "pending_id": pending.id,
                    "response": pending.proposed_message,
                })
        
        self._confirmation_manager.add_callback(on_change)
        
        while self._monitoring:
            await asyncio.sleep(1)
    
    async def _auto_send_after_timeout(self, pending_id: str) -> None:
        """Auto-send response after confirmation timeout."""
        await asyncio.sleep(self.config.response_timeout_seconds)
        
        pending = await self._confirmation_manager.get_pending(pending_id)
        if pending and pending.status == PendingResponseStatus.PENDING:
            pending.status = PendingResponseStatus.AUTO_SENT
            await self._send_response(pending.proposed_message)
    
    async def _check_cooldown(self) -> bool:
        """Check if we're past the response cooldown period."""
        async with self._cooldown_lock:
            if self._last_response_time is None:
                return True
            
            elapsed = (datetime.utcnow() - self._last_response_time).total_seconds()
            if elapsed < self.config.response_cooldown_seconds:
                return False
            
            self._last_response_time = datetime.utcnow()
            return True
    
    async def _transcribe_segment(self, segment: ProcessedSegment) -> str | None:
        """Transcribe audio segment using ASR."""
        try:
            # Save to temp file for ASR
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                sf.write(f.name, segment.audio, segment.sample_rate)
                temp_path = f.name
            
            # ASR
            if self.config.asr_model == "voxtral":
                from shakods.audio.asr import transcribe_audio_voxtral
                transcript = transcribe_audio_voxtral(
                    temp_path,
                    language=self.config.asr_language
                )
            else:
                # Fallback to whisper
                import whisper
                model = whisper.load_model("base")
                result = model.transcribe(temp_path)
                transcript = result["text"]
            
            Path(temp_path).unlink(missing_ok=True)
            return transcript.strip() if transcript else None
            
        except Exception as e:
            logger.exception(f"ASR failed: {e}")
            return None
    
    async def _generate_response_text(self, incoming_message: str) -> str:
        """Generate response text based on incoming message."""
        # Simple acknowledgment for now
        # TODO: Integrate with LLM for intelligent responses
        return f"Acknowledged: {incoming_message[:50]}... Standing by."
    
    async def _send_response(self, message: str) -> bool:
        """Send response via radio."""
        if not self.response_agent:
            logger.warning("No response agent configured")
            return False
        
        # Check PTT coordination
        if self.config.ptt_coordination_enabled and self.rig_manager:
            # Wait for PTT to be released
            max_wait = 5.0
            waited = 0.0
            while await self.rig_manager.is_ptt_active():
                if waited >= max_wait:
                    logger.warning("PTT remained active, aborting response")
                    return False
                await asyncio.sleep(0.1)
                waited += 0.1
        
        # Execute response
        task = {
            "transmission_type": "voice",
            "message": message,
            "use_tts": True,
        }
        
        try:
            result = await self.response_agent.execute(task)
            return result.get("success", False)
        except Exception as e:
            logger.exception(f"Response send failed: {e}")
            return False
    
    # Action handlers for confirmation management
    async def _action_approve_response(self, task: dict[str, Any]) -> dict[str, Any]:
        pending_id = task.get("pending_id")
        operator = task.get("operator")
        
        if not pending_id:
            return {"error": "pending_id required"}
        
        pending = await self._confirmation_manager.approve(pending_id, operator)
        if not pending:
            return {"error": "Pending response not found"}
        
        return {"success": True, "pending": pending.model_dump()}
    
    async def _action_reject_response(self, task: dict[str, Any]) -> dict[str, Any]:
        pending_id = task.get("pending_id")
        operator = task.get("operator")
        notes = task.get("notes")
        
        if not pending_id:
            return {"error": "pending_id required"}
        
        pending = await self._confirmation_manager.reject(pending_id, operator, notes)
        if not pending:
            return {"error": "Pending response not found"}
        
        return {"success": True, "pending": pending.model_dump()}
    
    async def _action_list_pending(self) -> dict[str, Any]:
        pending = await self._confirmation_manager.list_pending()
        return {
            "pending_responses": [p.model_dump() for p in pending],
            "count": len(pending),
        }
    
    async def _action_get_pending(self, task: dict[str, Any]) -> dict[str, Any]:
        pending_id = task.get("pending_id")
        pending = await self._confirmation_manager.get_pending(pending_id)
        if not pending:
            return {"error": "Not found"}
        return {"pending": pending.model_dump()}
```

---

## 6. Human-in-the-Loop Controls

### 6.1 PTT Coordination Module

```python
# shakods/shakods/radio/ptt_coordinator.py

"""PTT coordination for half-duplex operation."""

import asyncio
from enum import Enum, auto
from typing import Any

from loguru import logger


class RadioState(Enum):
    """Radio state machine for half-duplex coordination."""
    RX = auto()           # Receiving
    RX_PROCESSING = auto()  # Processing received audio
    TX_PENDING = auto()   # Response queued, awaiting confirmation
    TX_ACTIVE = auto()    # Currently transmitting
    TX_COOLDOWN = auto()  # Post-transmission cooldown


class PTTCoordinator:
    """
    Coordinates PTT state to prevent keying over existing transmissions
    and manages half-duplex state machine.
    """
    
    def __init__(
        self,
        rig_manager: Any,
        cooldown_ms: int = 500,
        break_in_enabled: bool = True,
    ):
        self.rig_manager = rig_manager
        self.cooldown_ms = cooldown_ms
        self.break_in_enabled = break_in_enabled
        
        self._state = RadioState.RX
        self._state_lock = asyncio.Lock()
        self._break_in_event = asyncio.Event()
        
    async def get_state(self) -> RadioState:
        """Get current radio state."""
        async with self._state_lock:
            return self._state
    
    async def request_transmit(self) -> bool:
        """
        Request permission to transmit.
        
        Returns True if granted, False if denied (e.g., break-in or busy).
        """
        async with self._state_lock:
            if self._state in (RadioState.TX_ACTIVE, RadioState.TX_PENDING):
                logger.warning("TX request denied: already transmitting")
                return False
            
            if self._state == RadioState.RX_PROCESSING:
                logger.info("TX requested while processing RX, waiting...")
                # Wait for processing to complete
                await asyncio.wait_for(
                    self._wait_for_state(RadioState.RX),
                    timeout=5.0
                )
            
            # Check if PTT is active (someone else transmitting)
            if await self.rig_manager.is_ptt_active():
                logger.warning("TX request denied: channel busy")
                return False
            
            self._state = RadioState.TX_PENDING
            return True
    
    async def begin_transmit(self) -> bool:
        """Begin actual transmission (set PTT)."""
        async with self._state_lock:
            if self._state != RadioState.TX_PENDING:
                return False
            
            await self.rig_manager.set_ptt(True)
            self._state = RadioState.TX_ACTIVE
            logger.info("PTT activated")
            return True
    
    async def end_transmit(self) -> None:
        """End transmission (release PTT)."""
        async with self._state_lock:
            if self._state == RadioState.TX_ACTIVE:
                await self.rig_manager.set_ptt(False)
                self._state = RadioState.TX_COOLDOWN
                logger.info("PTT released")
                
                # Start cooldown
                asyncio.create_task(self._cooldown_task())
    
    async def break_in(self) -> None:
        """
        Emergency break-in: cancel any pending/processing transmission.
        Called when operator manually keys PTT.
        """
        if not self.break_in_enabled:
            return
        
        async with self._state_lock:
            if self._state in (RadioState.TX_ACTIVE, RadioState.TX_PENDING):
                if self._state == RadioState.TX_ACTIVE:
                    await self.rig_manager.set_ptt(False)
                self._state = RadioState.RX
                self._break_in_event.set()
                logger.warning("Break-in activated by operator")
    
    async def _cooldown_task(self) -> None:
        """Cooldown period after transmission."""
        await asyncio.sleep(self.cooldown_ms / 1000)
        async with self._state_lock:
            if self._state == RadioState.TX_COOLDOWN:
                self._state = RadioState.RX
                logger.debug("TX cooldown complete")
    
    async def _wait_for_state(self, target_state: RadioState) -> None:
        """Wait for radio to reach target state."""
        while True:
            async with self._state_lock:
                if self._state == target_state:
                    return
            await asyncio.sleep(0.05)
```

---

## 7. Web Configuration Interface (TypeScript/React)

### 7.1 Interface Architecture

```
web-interface/
├── src/
│   ├── components/           # Reusable UI components
│   │   ├── common/          # Buttons, inputs, modals
│   │   ├── audio/           # Audio monitoring, VAD viz
│   │   ├── radio/           # Frequency, mode, PTT controls
│   │   └── config/          # Configuration forms
│   ├── features/            # Feature-specific modules
│   │   ├── audio/           # Audio pipeline config
│   │   ├── triggers/        # Trigger phrase management
│   │   ├── responses/       # Response mode & confirmation queue
│   │   └── system/          # System settings
│   ├── hooks/               # Custom React hooks
│   ├── services/            # API clients
│   ├── store/               # Zustand/Jotai state management
│   ├── types/               # TypeScript definitions
│   └── utils/               # Utilities
├── public/
└── package.json
```

### 7.2 Type Definitions

```typescript
// web-interface/src/types/audio.ts

export enum ResponseMode {
  LISTEN_ONLY = 'listen_only',
  CONFIRM_FIRST = 'confirm_first',
  CONFIRM_TIMEOUT = 'confirm_timeout',
  AUTO_RESPOND = 'auto_respond',
}

export enum VADMode {
  NORMAL = 'normal',
  LOW_BITRATE = 'low',
  AGGRESSIVE = 'aggressive',
  VERY_AGGRESSIVE = 'very_aggressive',
}

export enum TriggerMatchMode {
  EXACT = 'exact',
  CONTAINS = 'contains',
  STARTS_WITH = 'starts_with',
  FUZZY = 'fuzzy',
}

export enum PendingResponseStatus {
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  EXPIRED = 'expired',
  AUTO_SENT = 'auto_sent',
}

export interface AudioConfig {
  // Input/Output
  input_device: string | null;
  input_sample_rate: number;
  output_device: string | null;
  
  // Preprocessing
  preprocessing_enabled: boolean;
  agc_enabled: boolean;
  agc_target_rms: number;
  highpass_filter_enabled: boolean;
  highpass_cutoff_hz: number;
  
  // Denoising
  denoising_enabled: boolean;
  denoising_backend: 'rnnoise' | 'spectral' | 'none';
  noise_calibration_seconds: number;
  min_snr_db: number;
  
  // VAD
  vad_enabled: boolean;
  vad_mode: VADMode;
  pre_speech_buffer_ms: number;
  post_speech_buffer_ms: number;
  min_speech_duration_ms: number;
  max_speech_duration_ms: number;
  silence_duration_ms: number;
  
  // ASR
  asr_model: string;
  asr_language: string;
  asr_min_confidence: number;
  
  // Response behavior
  response_mode: ResponseMode;
  response_timeout_seconds: number;
  response_delay_ms: number;
  response_cooldown_seconds: number;
  
  // Trigger filtering
  trigger_enabled: boolean;
  trigger_phrases: string[];
  trigger_match_mode: TriggerMatchMode;
  trigger_callsign: string | null;
  trigger_min_confidence: number;
  
  // PTT coordination
  ptt_coordination_enabled: boolean;
  ptt_cooldown_ms: number;
  break_in_enabled: boolean;
}

export interface PendingResponse {
  id: string;
  created_at: string;
  expires_at: string;
  incoming_transcript: string;
  incoming_audio_path: string | null;
  frequency_hz: number | null;
  mode: string | null;
  proposed_message: string;
  proposed_audio_path: string | null;
  status: PendingResponseStatus;
  responded_at: string | null;
  responded_by: string | null;
  notes: string | null;
}

export interface AudioDevice {
  id: string | number;
  name: string;
  is_default: boolean;
  channels: number;
  sample_rates: number[];
}

export interface AudioMetrics {
  timestamp: string;
  input_level_db: number;
  output_level_db: number;
  vad_active: boolean;
  snr_db: number | null;
  is_speech: boolean;
}
```

### 7.3 API Service

```typescript
// web-interface/src/services/shakodsApi.ts

import { AudioConfig, AudioDevice, PendingResponse, AudioMetrics } from '../types/audio';

const API_BASE = process.env.REACT_APP_SHAKODS_API || 'http://localhost:8000';

class ShakodsApi {
  private baseUrl: string;
  
  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }
  
  // Configuration
  async getConfig(): Promise<AudioConfig> {
    const response = await fetch(`${this.baseUrl}/api/v1/config/audio`);
    if (!response.ok) throw new Error('Failed to fetch config');
    return response.json();
  }
  
  async updateConfig(config: Partial<AudioConfig>): Promise<AudioConfig> {
    const response = await fetch(`${this.baseUrl}/api/v1/config/audio`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    if (!response.ok) throw new Error('Failed to update config');
    return response.json();
  }
  
  async resetConfig(): Promise<AudioConfig> {
    const response = await fetch(`${this.baseUrl}/api/v1/config/audio/reset`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error('Failed to reset config');
    return response.json();
  }
  
  // Audio Devices
  async listAudioDevices(): Promise<AudioDevice[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/audio/devices`);
    if (!response.ok) throw new Error('Failed to fetch devices');
    return response.json();
  }
  
  async testAudioDevice(deviceId: string): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${this.baseUrl}/api/v1/audio/devices/${deviceId}/test`, {
      method: 'POST',
    });
    return response.json();
  }
  
  // Monitoring
  async startMonitoring(params: {
    frequency?: number;
    mode?: string;
    duration_seconds?: number;
  }): Promise<{ session_id: string }> {
    const response = await fetch(`${this.baseUrl}/api/v1/audio/monitor`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!response.ok) throw new Error('Failed to start monitoring');
    return response.json();
  }
  
  async stopMonitoring(sessionId: string): Promise<void> {
    await fetch(`${this.baseUrl}/api/v1/audio/monitor/${sessionId}`, {
      method: 'DELETE',
    });
  }
  
  // Confirmation Queue
  async listPendingResponses(): Promise<PendingResponse[]> {
    const response = await fetch(`${this.baseUrl}/api/v1/audio/pending`);
    if (!response.ok) throw new Error('Failed to fetch pending');
    const data = await response.json();
    return data.pending_responses;
  }
  
  async approveResponse(
    pendingId: string,
    operator?: string
  ): Promise<PendingResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/audio/pending/${pendingId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operator }),
    });
    if (!response.ok) throw new Error('Failed to approve');
    const data = await response.json();
    return data.pending;
  }
  
  async rejectResponse(
    pendingId: string,
    operator?: string,
    notes?: string
  ): Promise<PendingResponse> {
    const response = await fetch(`${this.baseUrl}/api/v1/audio/pending/${pendingId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operator, notes }),
    });
    if (!response.ok) throw new Error('Failed to reject');
    const data = await response.json();
    return data.pending;
  }
  
  // WebSocket for real-time metrics
  connectMetricsWebSocket(sessionId: string): WebSocket {
    const wsUrl = this.baseUrl.replace('http', 'ws');
    return new WebSocket(`${wsUrl}/ws/audio/metrics/${sessionId}`);
  }
}

export const shakodsApi = new ShakodsApi();
```

### 7.4 React Components

```tsx
// web-interface/src/components/audio/ResponseModeSelector.tsx

import React from 'react';
import { ResponseMode } from '../../types/audio';

interface ResponseModeSelectorProps {
  value: ResponseMode;
  onChange: (mode: ResponseMode) => void;
  disabled?: boolean;
}

const modeDescriptions: Record<ResponseMode, { label: string; description: string; warning?: string }> = {
  [ResponseMode.LISTEN_ONLY]: {
    label: 'Listen Only',
    description: 'Transcribe audio but never transmit responses. Safe for monitoring.',
  },
  [ResponseMode.CONFIRM_FIRST]: {
    label: 'Confirm First',
    description: 'Queue responses for operator approval before transmitting.',
  },
  [ResponseMode.CONFIRM_TIMEOUT]: {
    label: 'Confirm with Timeout',
    description: 'Queue responses but auto-send if not reviewed within timeout.',
    warning: 'Responses may be sent without human review if timeout expires.',
  },
  [ResponseMode.AUTO_RESPOND]: {
    label: 'Auto Respond',
    description: 'Automatically transmit responses without confirmation.',
    warning: 'WARNING: System will transmit immediately. Use with caution on shared frequencies.',
  },
};

export const ResponseModeSelector: React.FC<ResponseModeSelectorProps> = ({
  value,
  onChange,
  disabled = false,
}) => {
  return (
    <div className="space-y-4">
      <label className="block text-sm font-medium text-gray-700">
        Response Mode
      </label>
      
      <div className="grid grid-cols-1 gap-3">
        {(Object.keys(ResponseMode) as ResponseMode[]).map((mode) => {
          const config = modeDescriptions[mode];
          return (
            <label
              key={mode}
              className={`
                relative flex cursor-pointer rounded-lg border p-4 shadow-sm
                ${value === mode ? 'border-blue-500 ring-1 ring-blue-500' : 'border-gray-300'}
                ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
                ${mode === ResponseMode.AUTO_RESPOND ? 'border-red-300 bg-red-50' : ''}
              `}
            >
              <input
                type="radio"
                name="response-mode"
                value={mode}
                checked={value === mode}
                onChange={() => onChange(mode)}
                disabled={disabled}
                className="sr-only"
              />
              <div className="flex flex-1">
                <div className="flex flex-col">
                  <span className={`
                    block text-sm font-medium
                    ${mode === ResponseMode.AUTO_RESPOND ? 'text-red-900' : 'text-gray-900'}
                  `}>
                    {config.label}
                  </span>
                  <span className="mt-1 flex items-center text-sm text-gray-500">
                    {config.description}
                  </span>
                  {config.warning && (
                    <span className={`
                      mt-2 text-xs font-medium
                      ${mode === ResponseMode.AUTO_RESPOND ? 'text-red-600' : 'text-yellow-600'}
                    `}>
                      ⚠️ {config.warning}
                    </span>
                  )}
                </div>
              </div>
              {value === mode && (
                <div className="flex-shrink-0 text-blue-600">
                  <CheckIcon className="h-5 w-5" />
                </div>
              )}
            </label>
          );
        })}
      </div>
    </div>
  );
};

// Icon component
const CheckIcon: React.FC<{ className?: string }> = ({ className }) => (
  <svg className={className} fill="currentColor" viewBox="0 0 20 20">
    <path
      fillRule="evenodd"
      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
      clipRule="evenodd"
    />
  </svg>
);
```

```tsx
// web-interface/src/components/audio/ConfirmationQueue.tsx

import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { shakodsApi } from '../../services/shakodsApi';
import { PendingResponse, PendingResponseStatus } from '../../types/audio';

export const ConfirmationQueue: React.FC = () => {
  const queryClient = useQueryClient();
  const [autoRefresh, setAutoRefresh] = useState(true);
  
  const { data: pendingResponses = [], isLoading } = useQuery({
    queryKey: ['pendingResponses'],
    queryFn: () => shakodsApi.listPendingResponses(),
    refetchInterval: autoRefresh ? 1000 : false,
  });
  
  const approveMutation = useMutation({
    mutationFn: ({ id, operator }: { id: string; operator?: string }) =>
      shakodsApi.approveResponse(id, operator),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pendingResponses'] });
    },
  });
  
  const rejectMutation = useMutation({
    mutationFn: ({ id, operator, notes }: { id: string; operator?: string; notes?: string }) =>
      shakodsApi.rejectResponse(id, operator, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pendingResponses'] });
    },
  });
  
  const handleApprove = (id: string) => {
    const operator = prompt('Enter operator call sign (optional):');
    approveMutation.mutate({ id, operator: operator || undefined });
  };
  
  const handleReject = (id: string) => {
    const notes = prompt('Enter rejection reason (optional):');
    const operator = prompt('Enter operator call sign (optional):');
    rejectMutation.mutate({ id, operator: operator || undefined, notes: notes || undefined });
  };
  
  const getTimeRemaining = (expiresAt: string): string => {
    const expires = new Date(expiresAt);
    const now = new Date();
    const diff = expires.getTime() - now.getTime();
    
    if (diff <= 0) return 'Expired';
    
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    
    if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    }
    return `${seconds}s`;
  };
  
  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold text-gray-900">
          Response Confirmation Queue
        </h2>
        <label className="flex items-center space-x-2">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
            className="rounded border-gray-300"
          />
          <span className="text-sm text-gray-600">Auto-refresh</span>
        </label>
      </div>
      
      {isLoading ? (
        <div className="text-center py-8 text-gray-500">Loading...</div>
      ) : pendingResponses.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          No pending responses awaiting confirmation.
        </div>
      ) : (
        <div className="space-y-4">
          {pendingResponses.map((response) => (
            <div
              key={response.id}
              className="border rounded-lg p-4 hover:bg-gray-50 transition-colors"
            >
              <div className="flex justify-between items-start mb-2">
                <div>
                  <span className="text-xs text-gray-500">
                    ID: {response.id.slice(0, 8)}
                  </span>
                  <div className="text-sm text-gray-600">
                    Received: {new Date(response.created_at).toLocaleTimeString()}
                  </div>
                </div>
                <div className="text-right">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                    ⏱️ {getTimeRemaining(response.expires_at)}
                  </span>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 my-4">
                <div className="bg-blue-50 p-3 rounded">
                  <div className="text-xs font-medium text-blue-700 mb-1">
                    Incoming
                  </div>
                  <div className="text-sm text-blue-900">
                    {response.incoming_transcript}
                  </div>
                </div>
                
                <div className="bg-green-50 p-3 rounded">
                  <div className="text-xs font-medium text-green-700 mb-1">
                    Proposed Response
                  </div>
                  <div className="text-sm text-green-900">
                    {response.proposed_message}
                  </div>
                </div>
              </div>
              
              {response.frequency_hz && (
                <div className="text-xs text-gray-500 mb-3">
                  Frequency: {(response.frequency_hz / 1e6).toFixed(3)} MHz
                  {response.mode && ` | Mode: ${response.mode}`}
                </div>
              )}
              
              <div className="flex space-x-3">
                <button
                  onClick={() => handleApprove(response.id)}
                  disabled={approveMutation.isPending}
                  className="flex-1 bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 disabled:opacity-50 transition-colors"
                >
                  {approveMutation.isPending ? 'Approving...' : '✓ Approve & Send'}
                </button>
                <button
                  onClick={() => handleReject(response.id)}
                  disabled={rejectMutation.isPending}
                  className="flex-1 bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700 disabled:opacity-50 transition-colors"
                >
                  {rejectMutation.isPending ? 'Rejecting...' : '✗ Reject'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
```

```tsx
// web-interface/src/components/audio/VADVisualizer.tsx

import React, { useEffect, useRef, useState } from 'react';

interface VADVisualizerProps {
  websocketUrl: string;
}

interface AudioMetrics {
  timestamp: string;
  input_level_db: number;
  vad_active: boolean;
  snr_db: number | null;
  is_speech: boolean;
}

export const VADVisualizer: React.FC<VADVisualizerProps> = ({ websocketUrl }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [connected, setConnected] = useState(false);
  const [metrics, setMetrics] = useState<AudioMetrics | null>(null);
  const historyRef = useRef<number[]>(new Array(200).fill(-60));
  
  useEffect(() => {
    const ws = new WebSocket(websocketUrl);
    
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (event) => {
      const data: AudioMetrics = JSON.parse(event.data);
      setMetrics(data);
      
      // Update history
      historyRef.current.push(data.input_level_db);
      historyRef.current.shift();
    };
    
    return () => ws.close();
  }, [websocketUrl]);
  
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    const draw = () => {
      const width = canvas.width;
      const height = canvas.height;
      
      // Clear
      ctx.fillStyle = '#1f2937';
      ctx.fillRect(0, 0, width, height);
      
      // Draw grid
      ctx.strokeStyle = '#374151';
      ctx.lineWidth = 1;
      for (let i = 0; i <= 10; i++) {
        const y = (height / 10) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }
      
      // Draw waveform
      ctx.strokeStyle = metrics?.is_speech ? '#10b981' : '#60a5fa';
      ctx.lineWidth = 2;
      ctx.beginPath();
      
      const history = historyRef.current;
      const step = width / history.length;
      
      history.forEach((db, i) => {
        // Map dB (-60 to 0) to canvas height
        const normalized = Math.max(0, Math.min(1, (db + 60) / 60));
        const y = height - (normalized * height);
        
        if (i === 0) {
          ctx.moveTo(0, y);
        } else {
          ctx.lineTo(i * step, y);
        }
      });
      
      ctx.stroke();
      
      // Draw VAD indicator
      if (metrics?.vad_active) {
        ctx.fillStyle = metrics.is_speech ? '#ef4444' : '#fbbf24';
        ctx.beginPath();
        ctx.arc(width - 20, 20, 8, 0, Math.PI * 2);
        ctx.fill();
        
        ctx.fillStyle = '#fff';
        ctx.font = '12px sans-serif';
        ctx.fillText(metrics.is_speech ? 'SPEECH' : 'NOISE', width - 70, 25);
      }
      
      requestAnimationFrame(draw);
    };
    
    draw();
  }, [metrics]);
  
  return (
    <div className="bg-gray-900 rounded-lg p-4">
      <div className="flex justify-between items-center mb-2">
        <h3 className="text-white font-medium">Audio Monitor</h3>
        <div className="flex items-center space-x-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-gray-400 text-sm">
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>
      
      <canvas
        ref={canvasRef}
        width={600}
        height={150}
        className="w-full rounded"
      />
      
      {metrics && (
        <div className="grid grid-cols-3 gap-4 mt-3 text-sm">
          <div>
            <span className="text-gray-400">Level:</span>
            <span className="text-white ml-1">{metrics.input_level_db.toFixed(1)} dB</span>
          </div>
          <div>
            <span className="text-gray-400">SNR:</span>
            <span className="text-white ml-1">
              {metrics.snr_db?.toFixed(1) ?? '--'} dB
            </span>
          </div>
          <div>
            <span className="text-gray-400">Status:</span>
            <span className={`ml-1 ${metrics.is_speech ? 'text-green-400' : 'text-blue-400'}`}>
              {metrics.is_speech ? 'SPEECH' : 'SILENCE'}
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
```

### 7.5 Main Configuration Page

```tsx
// web-interface/src/pages/AudioConfigPage.tsx

import React from 'react';
import { useForm, Controller } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { shakodsApi } from '../services/shakodsApi';
import { AudioConfig, ResponseMode } from '../types/audio';
import { ResponseModeSelector } from '../components/audio/ResponseModeSelector';
import { ConfirmationQueue } from '../components/audio/ConfirmationQueue';
import { VADVisualizer } from '../components/audio/VADVisualizer';

export const AudioConfigPage: React.FC = () => {
  const queryClient = useQueryClient();
  
  const { data: config, isLoading } = useQuery({
    queryKey: ['config'],
    queryFn: () => shakodsApi.getConfig(),
  });
  
  const updateMutation = useMutation({
    mutationFn: (data: Partial<AudioConfig>) => shakodsApi.updateConfig(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['config'] });
    },
  });
  
  const { control, handleSubmit, watch } = useForm<AudioConfig>({
    defaultValues: config,
    values: config,
  });
  
  const responseMode = watch('response_mode');
  
  if (isLoading) {
    return <div className="p-8">Loading configuration...</div>;
  }
  
  return (
    <div className="max-w-7xl mx-auto p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">
        SHAKODS Audio Configuration
      </h1>
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left column: Configuration */}
        <div className="space-y-6">
          <form onSubmit={handleSubmit((data) => updateMutation.mutate(data))}>
            {/* Response Mode */}
            <div className="bg-white shadow rounded-lg p-6 mb-6">
              <Controller
                name="response_mode"
                control={control}
                render={({ field }) => (
                  <ResponseModeSelector
                    value={field.value}
                    onChange={field.onChange}
                  />
                )}
              />
            </div>
            
            {/* Trigger Configuration */}
            <div className="bg-white shadow rounded-lg p-6 mb-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                Trigger Phrases
              </h3>
              
              <div className="space-y-4">
                <Controller
                  name="trigger_enabled"
                  control={control}
                  render={({ field }) => (
                    <label className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={field.value}
                        onChange={field.onChange}
                        className="rounded border-gray-300"
                      />
                      <span>Enable trigger filtering</span>
                    </label>
                  )}
                />
                
                <Controller
                  name="trigger_phrases"
                  control={control}
                  render={({ field }) => (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Trigger Phrases (comma-separated)
                      </label>
                      <input
                        type="text"
                        value={field.value?.join(', ')}
                        onChange={(e) => field.onChange(
                          e.target.value.split(',').map(s => s.trim()).filter(Boolean)
                        )}
                        className="w-full border rounded px-3 py-2"
                        placeholder="shakods, field station"
                      />
                    </div>
                  )}
                />
                
                <Controller
                  name="trigger_callsign"
                  control={control}
                  render={({ field }) => (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Station Callsign Filter (optional)
                      </label>
                      <input
                        type="text"
                        value={field.value || ''}
                        onChange={field.onChange}
                        className="w-full border rounded px-3 py-2"
                        placeholder="N0CALL"
                      />
                    </div>
                  )}
                />
              </div>
            </div>
            
            {/* VAD Configuration */}
            <div className="bg-white shadow rounded-lg p-6 mb-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                Voice Activity Detection
              </h3>
              
              <div className="grid grid-cols-2 gap-4">
                <Controller
                  name="vad_mode"
                  control={control}
                  render={({ field }) => (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        VAD Aggressiveness
                      </label>
                      <select
                        value={field.value}
                        onChange={field.onChange}
                        className="w-full border rounded px-3 py-2"
                      >
                        <option value="normal">Normal</option>
                        <option value="low">Low Bitrate</option>
                        <option value="aggressive">Aggressive</option>
                        <option value="very_aggressive">Very Aggressive</option>
                      </select>
                    </div>
                  )}
                />
                
                <Controller
                  name="min_snr_db"
                  control={control}
                  render={({ field }) => (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Min SNR (dB)
                      </label>
                      <input
                        type="number"
                        value={field.value}
                        onChange={(e) => field.onChange(parseFloat(e.target.value))}
                        className="w-full border rounded px-3 py-2"
                        min="-10"
                        max="40"
                        step="0.5"
                      />
                    </div>
                  )}
                />
              </div>
            </div>
            
            {/* Submit */}
            <div className="flex space-x-3">
              <button
                type="submit"
                disabled={updateMutation.isPending}
                className="flex-1 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {updateMutation.isPending ? 'Saving...' : 'Save Configuration'}
              </button>
              
              <button
                type="button"
                onClick={() => shakodsApi.resetConfig()}
                className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-50"
              >
                Reset to Defaults
              </button>
            </div>
          </form>
        </div>
        
        {/* Right column: Monitoring & Queue */}
        <div className="space-y-6">
          {/* VAD Visualizer */}
          <VADVisualizer websocketUrl="ws://localhost:8000/ws/audio/metrics/live" />
          
          {/* Confirmation Queue */}
          {responseMode === ResponseMode.CONFIRM_FIRST ||
           responseMode === ResponseMode.CONFIRM_TIMEOUT ? (
            <ConfirmationQueue />
          ) : null}
        </div>
      </div>
    </div>
  );
};
```

### 7.6 Backend API Routes (FastAPI)

```python
# shakods/shakods/api/routes/audio.py

"""Audio configuration and control API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, WebSocket, HTTPException

from shakods.config.schema import AudioConfig, PendingResponse
from shakods.dependencies import get_config, get_audio_agent
from shakods.specialized.radio_rx_audio import RadioAudioReceptionAgent

router = APIRouter(prefix="/audio", tags=["audio"])


@router.get("/config", response_model=AudioConfig)
async def get_audio_config(config: AudioConfig = Depends(get_config)) -> AudioConfig:
    """Get current audio configuration."""
    return config.audio


@router.patch("/config", response_model=AudioConfig)
async def update_audio_config(
    updates: dict[str, Any],
    config: AudioConfig = Depends(get_config),
) -> AudioConfig:
    """Update audio configuration (partial)."""
    for key, value in updates.items():
        if hasattr(config.audio, key):
            setattr(config.audio, key, value)
    # TODO: Persist config
    return config.audio


@router.post("/config/reset", response_model=AudioConfig)
async def reset_audio_config(
    config: AudioConfig = Depends(get_config),
) -> AudioConfig:
    """Reset audio configuration to defaults."""
    config.audio = AudioConfig()
    return config.audio


@router.get("/devices")
async def list_audio_devices() -> list[dict[str, Any]]:
    """List available audio input/output devices."""
    try:
        import sounddevice as sd
        devices = []
        for i, dev in enumerate(sd.query_devices()):
            devices.append({
                "id": i,
                "name": dev["name"],
                "channels": dev["max_input_channels"],
                "sample_rates": [16000, 22050, 44100, 48000],
                "is_default": dev.get("default", False),
            })
        return devices
    except ImportError:
        raise HTTPException(500, "Audio subsystem not available")


@router.get("/pending", response_model=dict[str, Any])
async def list_pending_responses(
    agent: RadioAudioReceptionAgent = Depends(get_audio_agent),
) -> dict[str, Any]:
    """List pending responses awaiting confirmation."""
    return await agent.execute({"action": "list_pending"})


@router.post("/pending/{pending_id}/approve")
async def approve_response(
    pending_id: str,
    operator: str | None = None,
    agent: RadioAudioReceptionAgent = Depends(get_audio_agent),
) -> dict[str, Any]:
    """Approve a pending response."""
    return await agent.execute({
        "action": "approve_response",
        "pending_id": pending_id,
        "operator": operator,
    })


@router.post("/pending/{pending_id}/reject")
async def reject_response(
    pending_id: str,
    operator: str | None = None,
    notes: str | None = None,
    agent: RadioAudioReceptionAgent = Depends(get_audio_agent),
) -> dict[str, Any]:
    """Reject a pending response."""
    return await agent.execute({
        "action": "reject_response",
        "pending_id": pending_id,
        "operator": operator,
        "notes": notes,
    })


@router.websocket("/ws/metrics/{session_id}")
async def audio_metrics_websocket(
    websocket: WebSocket,
    session_id: str,
):
    """WebSocket for real-time audio metrics."""
    await websocket.accept()
    
    try:
        while True:
            # TODO: Get actual metrics from stream processor
            metrics = {
                "timestamp": datetime.utcnow().isoformat(),
                "input_level_db": -30.0,  # Placeholder
                "vad_active": True,
                "snr_db": 15.0,
                "is_speech": False,
            }
            await websocket.send_json(metrics)
            await asyncio.sleep(0.1)
    except Exception:
        await websocket.close()
```

---

## 8. Integration & Orchestration

### 8.1 Agent Registration

```python
# shakods/shakods/orchestrator/registry.py (additions)

from shakods.specialized.radio_rx_audio import RadioAudioReceptionAgent

def create_default_agents(config: Config) -> AgentRegistry:
    """Create and register default agents based on configuration."""
    registry = AgentRegistry()
    
    # ... existing agents ...
    
    # Audio reception agent (if voice_rx deps available and enabled)
    if config.radio.audio_input_enabled:
        try:
            from shakods.audio.stream_processor import AudioStreamProcessor
            from shakods.audio.capture import AudioCaptureService
            
            stream_processor = AudioStreamProcessor(
                sample_rate=config.audio.input_sample_rate,
                vad_aggressiveness={
                    "normal": 0, "low": 1, "aggressive": 2, "very_aggressive": 3
                }.get(config.audio.vad_mode, 2),
                # ... other config ...
            )
            
            capture_service = AudioCaptureService(
                stream_processor=stream_processor,
                input_device=config.audio.input_device,
                sample_rate=config.audio.input_sample_rate,
            )
            
            rx_audio_agent = RadioAudioReceptionAgent(
                config=config.audio,
                capture_service=capture_service,
                stream_processor=stream_processor,
                # ... rig_manager, response_agent ...
            )
            
            registry.register_agent(rx_audio_agent)
            logger.info("Registered RadioAudioReceptionAgent")
            
        except ImportError as e:
            logger.warning(f"Could not register RadioAudioReceptionAgent: {e}")
    
    return registry
```

### 8.2 REACT Loop Integration

```python
# shakods/shakods/orchestrator/react_loop.py (modifications)

async def _phase_acting(self, state: REACTState) -> None:
    """ACTING: Delegate to specialized agents with upstream callback."""
    for task in state.decomposed_tasks:
        if task.status != "pending":
            continue
        
        task.status = "in_progress"
        
        if self.agent_registry:
            task_dict = {**task.payload, "description": task.description}
            agent = self.agent_registry.get_agent_for_task(task_dict)
            
            if agent:
                try:
                    # Create upstream callback for this task
                    async def upstream_callback(event: UpstreamEvent) -> None:
                        # Store in state context for tracking
                        state.context.setdefault("events", []).append({
                            "task_id": task.task_id,
                            "event": event.model_dump(),
                        })
                        
                        # Emit via middleware if available
                        if self.middleware_pipeline:
                            await self.middleware_pipeline.emit(event)
                    
                    task.result = await agent.execute(task_dict, upstream_callback)
                    task.status = "completed"
                    
                except Exception as e:
                    logger.exception("Agent execution failed: %s", e)
                    task.status = "failed"
                    task.error = str(e)
                    state.failed_tasks.append(task)
            else:
                task.status = "completed"
                task.result = {"message": "No agent for task"}
        
        if task.status == "completed":
            state.completed_tasks.append(task)
    
    state.decomposed_tasks = [
        t for t in state.decomposed_tasks
        if t.status not in ("completed", "failed")
    ]
    state.phase = self._next_phase(state.phase)
```

---

## 9. Testing Strategy

### 9.1 Unit Tests

```python
# shakods/tests/unit/audio/test_stream_processor.py

import numpy as np
import pytest

from shakods.audio.stream_processor import (
    AudioPreprocessor,
    WebRTCVAD,
    AudioStreamProcessor,
    ProcessedSegment,
)


class TestAudioPreprocessor:
    def test_highpass_filter(self):
        preproc = AudioPreprocessor(sample_rate=16000, highpass_cutoff=80.0)
        # Create low-frequency signal
        t = np.linspace(0, 1, 16000)
        low_freq = np.sin(2 * np.pi * 30 * t)  # 30 Hz
        frame = low_freq[:480].astype(np.float32)
        
        result = preproc.process(frame)
        # High-pass should attenuate 30 Hz
        assert np.abs(result).mean() < np.abs(frame).mean()
    
    def test_agc_normalization(self):
        preproc = AudioPreprocessor(agc_target_rms=0.1)
        # Low amplitude signal
        frame = np.random.randn(480).astype(np.float32) * 0.01
        
        result = preproc.process(frame)
        # AGC should increase amplitude
        assert np.sqrt(np.mean(result**2)) > np.sqrt(np.mean(frame**2))


class TestWebRTCVAD:
    @pytest.fixture
    def vad(self):
        try:
            return WebRTCVAD(sample_rate=16000, aggressiveness=2)
        except ImportError:
            pytest.skip("webrtcvad not installed")
    
    def test_detects_speech(self, vad):
        # Create synthetic speech-like signal
        t = np.linspace(0, 0.03, int(16000 * 0.03))
        # Mix of frequencies (vowel-like)
        signal = (
            np.sin(2 * np.pi * 200 * t) * 0.5 +
            np.sin(2 * np.pi * 800 * t) * 0.3 +
            np.sin(2 * np.pi * 1500 * t) * 0.2
        )
        signal = signal.astype(np.float32) * 0.3
        
        is_speech = vad.is_speech(signal)
        assert isinstance(is_speech, bool)


class TestAudioStreamProcessor:
    @pytest.fixture
    def processor(self):
        return AudioStreamProcessor(
            sample_rate=16000,
            min_speech_duration_ms=500,
            silence_duration_ms=800,
        )
    
    @pytest.mark.asyncio
    async def test_segment_callback(self, processor):
        segments = []
        
        async def callback(segment):
            segments.append(segment)
        
        processor.set_segment_callback(callback)
        
        # Simulate speech segment
        # ... generate test frames ...
        
        assert len(segments) == 0  # No actual speech in test
```

### 9.2 Integration Tests

```python
# shakods/tests/integration/test_audio_loop.py

import pytest
import asyncio

@pytest.mark.asyncio
async def test_full_audio_loop():
    """Test complete Listen → ASR → Trigger → Confirm → TX flow."""
    
    # Setup test components
    config = AudioConfig(
        response_mode=ResponseMode.CONFIRM_FIRST,
        trigger_phrases=["test"],
    )
    
    # Mock components
    mock_rig = MockRigManager()
    mock_response_agent = MockResponseAgent()
    
    agent = RadioAudioReceptionAgent(
        config=config,
        rig_manager=mock_rig,
        response_agent=mock_response_agent,
        # ... capture and stream processor mocks ...
    )
    
    # Simulate incoming audio trigger
    result = await agent.execute({
        "action": "simulate_transcription",
        "transcript": "test message",
        "confidence": 0.9,
    })
    
    # Verify pending response created
    pending = await agent.execute({"action": "list_pending"})
    assert pending["count"] == 1
    
    # Approve response
    pending_id = pending["pending_responses"][0]["id"]
    await agent.execute({
        "action": "approve_response",
        "pending_id": pending_id,
        "operator": "TEST-OP",
    })
    
    # Verify response sent
    assert mock_response_agent.last_message is not None
```

---

## 10. Implementation Checklist

### Phase 1: Core Pipeline
- [ ] Add `voice_rx` optional dependencies (webrtcvad, rnnoise)
- [ ] Implement `AudioPreprocessor` (AGC, high-pass)
- [ ] Implement `NoiseSuppressor` (RNNoise + fallback)
- [ ] Implement `WebRTCVAD` wrapper
- [ ] Implement `AudioStreamProcessor` with state machine
- [ ] Update `AudioCaptureService` to use stream processor
- [ ] Unit tests for pipeline components

### Phase 2: Agent & Safety
- [ ] Extend configuration schema (`ResponseMode`, `TriggerMatchMode`, etc.)
- [ ] Implement `TriggerFilter` with phrase/callsign matching
- [ ] Implement `ConfirmationManager` with timeout handling
- [ ] Implement `PTTCoordinator` for half-duplex
- [ ] Implement `RadioAudioReceptionAgent` with all action handlers
- [ ] Add safety validations (cooldowns, SNR thresholds)
- [ ] Integration tests for agent

### Phase 3: Web Interface
- [ ] Set up TypeScript/React project structure
- [ ] Implement API client (`shakodsApi.ts`)
- [ ] Implement `ResponseModeSelector` component
- [ ] Implement `ConfirmationQueue` component
- [ ] Implement `VADVisualizer` component
- [ ] Implement main `AudioConfigPage`
- [ ] Add WebSocket support for real-time metrics
- [ ] Backend API routes (FastAPI)

### Phase 4: Integration
- [ ] Update `AgentRegistry` for audio agent registration
- [ ] Wire up REACT loop upstream callbacks
- [ ] Add audio monitoring to health checks
- [ ] Documentation and examples
- [ ] End-to-end testing

---

## Migration from v1.0

| v1.0 Component | v2.0 Replacement | Notes |
|----------------|------------------|-------|
| `AudioCaptureService` (RMS VAD) | `AudioCaptureService` + `AudioStreamProcessor` | WebSocket-style async processing |
| RMS-based VAD | WebRTC VAD | More robust, less false triggers |
| No denoising | `NoiseSuppressor` (RNNoise) | Better ASR in noisy environments |
| `auto_respond: bool` | `response_mode: ResponseMode` | Granular control with confirmation |
| No trigger filtering | `TriggerFilter` | Phrase/callsign matching |
| No confirmation queue | `ConfirmationManager` | Human-in-the-loop capability |
| No PTT coordination | `PTTCoordinator` | Half-duplex safety |
| No web UI | Full React interface | Real-time monitoring & control |

---

*Plan version: 2.0. Place this file in the shakods directory (.).*
