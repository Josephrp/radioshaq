"""Play audio to a sound device (e.g. rig line-in). Used for voice TX with CAT rigs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger


def play_audio_to_device(
    path: str | Path | None = None,
    audio_bytes: bytes | None = None,
    device: str | int | None = None,
) -> float:
    """
    Decode audio from file or bytes and play to the given sound device (blocking).

    Supports WAV, FLAC, OGG. For MP3, requires pydub (optional).
    Used for voice TX: play to the device wired to the rig's line-in while PTT is keyed.

    Args:
        path: Path to audio file (WAV/FLAC/OGG or MP3 if pydub available).
        audio_bytes: Raw audio bytes (format inferred from path if path is set; else not used).
        device: sounddevice output device (name or index). None = default device.

    Returns:
        Duration in seconds (for caller to hold PTT).

    Raises:
        RuntimeError: If playback deps (sounddevice, soundfile) not installed or playback fails.
    """
    try:
        import sounddevice as sd
    except ImportError:
        raise RuntimeError(
            "voice_tx playback requires sounddevice. Install with: uv sync --extra voice_tx (or pip install sounddevice)"
        ) from None

    data: Any
    sample_rate: int

    if path is not None:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(str(path))
        suffix = path.suffix.lower()
        if suffix == ".mp3":
            try:
                from pydub import AudioSegment
            except ImportError:
                raise RuntimeError(
                    "MP3 playback requires pydub. Install with: pip install pydub (and ffmpeg). Or convert file to WAV."
                ) from None
            seg = AudioSegment.from_mp3(str(path))
            data = seg.get_array_of_samples()
            import numpy as np
            data = np.array(data, dtype=np.float32) / (1 << 15)
            if seg.channels == 2:
                data = data.reshape(-1, 2).mean(axis=1)
            sample_rate = seg.frame_rate
        else:
            try:
                import soundfile as sf
            except ImportError:
                raise RuntimeError(
                    "WAV/FLAC/OGG playback requires soundfile. Install with: uv sync --extra voice_tx (or pip install soundfile)"
                ) from None
            data, sample_rate = sf.read(str(path), dtype="float32")
            if data.ndim == 2:
                data = data.mean(axis=1)
    elif audio_bytes is not None:
        try:
            import soundfile as sf
            import io
            data, sample_rate = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        except ImportError:
            raise RuntimeError(
                "Playing from bytes requires soundfile. Install with: uv sync --extra voice_tx (or pip install soundfile)"
            ) from None
        if data.ndim == 2:
            data = data.mean(axis=1)
    else:
        raise ValueError("Provide path or audio_bytes")

    duration_sec = len(data) / float(sample_rate)
    logger.debug("Playing {:.2f}s to device {}", duration_sec, device)
    sd.play(data, sample_rate, blocking=True, device=device)
    return duration_sec
