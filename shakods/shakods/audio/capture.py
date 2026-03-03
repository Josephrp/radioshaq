"""Audio capture from radio line-out with stream processing integration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable

import numpy as np
from loguru import logger

from shakods.audio.stream_processor import AudioStreamProcessor, ProcessedSegment


class AudioCaptureService:
    """
    Audio capture service that feeds into the stream processor.
    Captures from rig line-out and runs VAD/denoise pipeline; optionally
    supports legacy callback with temp WAV path when stream processor not used.
    """

    def __init__(
        self,
        stream_processor: AudioStreamProcessor | None = None,
        input_device: str | int | None = None,
        sample_rate: int = 16000,
        chunk_duration_ms: int = 30,
    ) -> None:
        self.stream_processor = stream_processor
        self.input_device = input_device
        self.sample_rate = sample_rate
        self.chunk_samples = int(sample_rate * chunk_duration_ms / 1000)

        self._running = False
        self._stream: Any = None
        self._capture_task: asyncio.Task[None] | None = None
        self._frame_queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=100)

    async def start(
        self,
        on_speech_captured: Callable[[Path], Awaitable[None]] | None = None,
    ) -> None:
        """Start audio capture. If stream_processor set, feed frames into it.
        If on_speech_captured is provided without stream_processor, not supported (use stream processor).
        """
        try:
            import sounddevice as sd
        except ImportError as e:
            raise RuntimeError(
                "sounddevice not installed. Run: uv sync --extra voice_rx"
            ) from e

        self._running = True

        def audio_callback(
            indata: np.ndarray,
            frames: int,
            time_info: Any,
            status: Any,
        ) -> None:
            if status:
                logger.warning("Audio callback status: %s", status)
            frame = indata[:, 0].copy().astype(np.float32)
            try:
                self._frame_queue.put_nowait(frame)
            except asyncio.QueueFull:
                pass

        self._stream = sd.InputStream(
            device=self.input_device,
            channels=1,
            samplerate=self.sample_rate,
            blocksize=self.chunk_samples,
            dtype=np.float32,
            callback=audio_callback,
        )
        self._stream.start()

        if self.stream_processor and on_speech_captured:
            async def on_segment(segment: ProcessedSegment) -> None:
                import tempfile
                import soundfile as sf
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    path = Path(f.name)
                sf.write(path, segment.audio, segment.sample_rate)
                try:
                    await on_speech_captured(path)
                finally:
                    path.unlink(missing_ok=True)

            self.stream_processor.set_segment_callback(on_segment)

        self._capture_task = asyncio.create_task(self._process_loop())
        logger.info("Audio capture started on device %s", self.input_device)

    async def _process_loop(self) -> None:
        """Main processing loop: dequeue frames and feed to stream processor."""
        while self._running and self.stream_processor:
            try:
                frame = await asyncio.wait_for(
                    self._frame_queue.get(),
                    timeout=1.0,
                )
                await self.stream_processor.process_frame(frame)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Frame processing error: %s", e)

    def stop(self) -> None:
        """Stop audio capture."""
        self._running = False
        if self._capture_task and not self._capture_task.done():
            self._capture_task.cancel()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        logger.info("Audio capture stopped")
