"""Real-time audio stream processor with denoising and VAD."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Awaitable, Callable

import numpy as np
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

    def __post_init__(self) -> None:
        if self.rms == 0.0 and len(self.samples) > 0:
            self.rms = float(np.sqrt(np.mean(self.samples.astype(np.float32) ** 2)))


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
    ) -> None:
        self.sample_rate = sample_rate
        self.agc_target_rms = agc_target_rms
        self.agc_max_gain = agc_max_gain
        self.highpass_cutoff = highpass_cutoff
        self._agc_gain = 1.0
        self._hp_state: np.ndarray = np.zeros(2)

    def process(self, frame: np.ndarray) -> np.ndarray:
        """Apply preprocessing chain to audio frame."""
        frame = self._highpass_filter(frame)
        frame = self._apply_agc(frame)
        max_val = np.max(np.abs(frame))
        if max_val > 0.99:
            frame = frame * (0.99 / max_val)
        return frame

    def _highpass_filter(self, samples: np.ndarray) -> np.ndarray:
        """Simple high-pass filter (remove rumble, hum)."""
        rc = 1.0 / (2 * np.pi * self.highpass_cutoff)
        alpha = rc / (rc + 1.0 / self.sample_rate)
        output = np.zeros_like(samples, dtype=np.float32)
        output[0] = float(samples[0] - self._hp_state[0])
        for i in range(1, len(samples)):
            output[i] = alpha * (output[i - 1] + float(samples[i] - samples[i - 1]))
        self._hp_state[0] = float(samples[-1])
        return output

    def _apply_agc(self, samples: np.ndarray) -> np.ndarray:
        """Adaptive gain control."""
        rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
        if rms > 0:
            target_gain = self.agc_target_rms / rms
            target_gain = min(target_gain, self.agc_max_gain)
            self._agc_gain = 0.9 * self._agc_gain + 0.1 * target_gain
        return samples * self._agc_gain


class NoiseSuppressor:
    """Noise suppression using noisereduce (spectral) or RNNoise if available."""

    def __init__(self, sample_rate: int = 16000, use_rnnoise: bool = True) -> None:
        self.sample_rate = sample_rate
        self.use_rnnoise = use_rnnoise
        self._rnnoise: Any = None
        self._noise_profile: deque[np.ndarray] = deque(maxlen=50)

        if use_rnnoise:
            try:
                import rnnoise  # type: ignore[import-untyped]
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
        if self.use_rnnoise and self._rnnoise is not None:
            try:
                out, prob = self._rnnoise.process_frame(frame)
                snr = 10.0 * np.log10(prob / (1.0 - prob + 1e-10)) if prob < 1.0 else 20.0
                return out, float(snr)
            except Exception:
                pass
        return self._spectral_subtraction(frame)

    def _spectral_subtraction(self, frame: np.ndarray) -> tuple[np.ndarray, float]:
        """Fallback spectral subtraction denoising."""
        try:
            import noisereduce as nr
            if len(self._noise_profile) >= 10:
                noise_clip = np.concatenate(list(self._noise_profile))
                # Match length for noisereduce
                min_len = min(len(frame), len(noise_clip))
                reduced = nr.reduce_noise(
                    y=frame[:min_len].astype(np.float32),
                    y_noise=noise_clip[:min_len].astype(np.float32),
                    sr=self.sample_rate,
                    prop_decrease=0.75,
                )
                var_orig = np.var(frame[:min_len])
                var_red = np.var(reduced)
                snr = 10.0 * np.log10(var_orig / (var_red + 1e-10))
                # Pad or truncate to match input frame length for caller (VAD expects frame_samples)
                if len(reduced) < len(frame):
                    reduced = np.pad(
                        reduced.astype(np.float32),
                        (0, len(frame) - len(reduced)),
                        mode="constant",
                        constant_values=0.0,
                    )
                else:
                    reduced = reduced[: len(frame)].astype(np.float32)
                return reduced, float(snr)
        except ImportError:
            pass
        return frame, 0.0


class WebRTCVAD:
    """WebRTC Voice Activity Detection wrapper."""

    def __init__(self, sample_rate: int = 16000, aggressiveness: int = 2) -> None:
        try:
            import webrtcvad
            self.vad = webrtcvad.Vad(aggressiveness)
        except ImportError as e:
            raise RuntimeError(
                "webrtcvad not installed. Run: uv sync --extra voice_rx"
            ) from e
        self.sample_rate = sample_rate
        self.frame_duration_ms = 30
        self.frame_samples = int(sample_rate * self.frame_duration_ms / 1000)

    def is_speech(self, frame: np.ndarray) -> bool:
        """Check if frame contains speech."""
        if len(frame) != self.frame_samples:
            return False
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
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_samples = int(sample_rate * frame_duration_ms / 1000)

        self.pre_speech_frames = int(pre_speech_buffer_ms / frame_duration_ms)
        self.post_speech_frames = int(post_speech_buffer_ms / frame_duration_ms)
        self.min_speech_frames = int(min_speech_duration_ms / frame_duration_ms)
        self.max_speech_frames = int(max_speech_duration_ms / frame_duration_ms)
        self.silence_frames = int(silence_duration_ms / frame_duration_ms)

        self.preprocessor = AudioPreprocessor(sample_rate=sample_rate)
        self.denoiser = NoiseSuppressor(sample_rate=sample_rate, use_rnnoise=use_rnnoise)
        self.vad = WebRTCVAD(sample_rate=sample_rate, aggressiveness=vad_aggressiveness)

        self._state = StreamState.IDLE
        self._ring_buffer: deque[np.ndarray] = deque(maxlen=max(1, self.pre_speech_frames))
        self._speech_buffer: list[np.ndarray] = []
        self._speech_frames = 0
        self._silence_frames = 0
        self._noise_calibration_active = True

        self._on_segment_ready: Callable[[ProcessedSegment], Awaitable[None]] | None = None

    def set_segment_callback(
        self,
        callback: Callable[[ProcessedSegment], Awaitable[None]],
    ) -> None:
        """Set callback for when a speech segment is ready."""
        self._on_segment_ready = callback

    async def process_frame(self, raw_frame: np.ndarray) -> None:
        """Process a single audio frame through the pipeline."""
        if len(raw_frame) != self.frame_samples:
            return
        frame = self.preprocessor.process(raw_frame)

        if self._noise_calibration_active:
            self.denoiser.calibrate_noise(frame)
            if len(self.denoiser._noise_profile) >= self.denoiser._noise_profile.maxlen:
                self._noise_calibration_active = False
                self._state = StreamState.LISTENING
                logger.info("Noise calibration complete")
            return

        denoised_frame, snr = self.denoiser.process(frame)
        if len(denoised_frame) != self.frame_samples:
            logger.warning(
                "Denoised frame length %s != %s, resizing may cause artifacts",
                len(denoised_frame),
                self.frame_samples,
            )
            denoised_frame = np.resize(denoised_frame, self.frame_samples)
        is_speech = self.vad.is_speech(denoised_frame)
        await self._update_state(is_speech, denoised_frame, snr)

    async def _update_state(
        self,
        is_speech: bool,
        frame: np.ndarray,
        snr: float,
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
            # Always append current frame (speech or silence) so we include post-speech tail
            self._speech_buffer.append(frame)
            if is_speech:
                self._speech_frames += 1
                self._silence_frames = 0
                if self._speech_frames >= self.max_speech_frames:
                    await self._finalize_segment(snr)
            else:
                self._silence_frames += 1
                if self._silence_frames >= self.silence_frames:
                    await self._finalize_segment(snr)
                # While _silence_frames <= post_speech_frames we keep appending (already done above)

    async def _finalize_segment(self, snr: float) -> None:
        """Finalize current speech segment and emit."""
        if len(self._speech_buffer) >= self.min_speech_frames:
            audio = np.concatenate(self._speech_buffer)
            duration_ms = len(audio) / self.sample_rate * 1000
            segment = ProcessedSegment(
                audio=audio,
                sample_rate=self.sample_rate,
                start_time_ms=0.0,
                end_time_ms=duration_ms,
                duration_ms=duration_ms,
                avg_rms=float(np.sqrt(np.mean(audio ** 2))),
                snr_db=snr,
            )
            if self._on_segment_ready:
                await self._on_segment_ready(segment)
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
