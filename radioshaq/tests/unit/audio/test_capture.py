"""Tests for AudioCaptureService."""

from __future__ import annotations

import pytest

pytest.importorskip("sounddevice")
pytest.importorskip("soundfile")

from radioshaq.audio.capture import AudioCaptureService
from radioshaq.audio.stream_processor import AudioStreamProcessor


def test_audio_capture_service_init_with_stream_processor() -> None:
    sp = AudioStreamProcessor(sample_rate=16000, frame_duration_ms=30)
    cap = AudioCaptureService(
        stream_processor=sp,
        input_device=None,
        sample_rate=16000,
        chunk_duration_ms=30,
    )
    assert cap.stream_processor is sp
    assert cap.sample_rate == 16000
    assert cap._running is False


@pytest.mark.asyncio
async def test_audio_capture_service_stop() -> None:
    sp = AudioStreamProcessor(sample_rate=16000, frame_duration_ms=30)
    cap = AudioCaptureService(stream_processor=sp)
    await cap.stop()
    assert cap._running is False
