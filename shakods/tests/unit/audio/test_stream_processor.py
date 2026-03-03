"""Tests for AudioStreamProcessor and related classes."""

from __future__ import annotations

import pytest
import numpy as np

pytest.importorskip("webrtcvad")

from shakods.audio.stream_processor import (
    AudioPreprocessor,
    AudioStreamProcessor,
    ProcessedSegment,
    StreamState,
)


def test_audio_preprocessor_process() -> None:
    pre = AudioPreprocessor(sample_rate=16000)
    frame = np.zeros(480, dtype=np.float32)
    frame[100:200] = 0.5
    out = pre.process(frame)
    assert out.shape == frame.shape
    assert np.any(np.abs(out) > 0)


def test_audio_stream_processor_init() -> None:
    proc = AudioStreamProcessor(
        sample_rate=16000,
        frame_duration_ms=30,
        vad_aggressiveness=2,
    )
    assert proc.sample_rate == 16000
    assert proc.frame_samples == 480
    assert proc._state == StreamState.IDLE


def test_audio_stream_processor_reset() -> None:
    proc = AudioStreamProcessor(sample_rate=16000, frame_duration_ms=30)
    proc._state = StreamState.SPEECH_DETECTED
    proc.reset()
    assert proc._state == StreamState.IDLE
    assert len(proc._speech_buffer) == 0


def test_processed_segment() -> None:
    audio = np.zeros(1600, dtype=np.float32)
    seg = ProcessedSegment(
        audio=audio,
        sample_rate=16000,
        start_time_ms=0.0,
        end_time_ms=100.0,
        duration_ms=100.0,
        avg_rms=0.0,
        snr_db=5.0,
    )
    assert seg.sample_rate == 16000
    assert seg.duration_ms == 100.0
