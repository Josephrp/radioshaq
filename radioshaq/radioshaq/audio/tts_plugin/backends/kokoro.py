"""Kokoro-82M local TTS backend. Requires: uv sync --extra tts_kokoro."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np


def _to_numpy(audio: object) -> np.ndarray:
    """Convert pipeline audio (tensor or array) to 1D numpy."""
    if hasattr(audio, "numpy"):
        return np.asarray(audio.numpy()).flatten()
    return np.asarray(audio).flatten()


class KokoroTTSBackend:
    """TTS via local Kokoro-82M. No API key; uses KPipeline (default model)."""

    def __init__(self) -> None:
        self._pipelines: dict[str, object] = {}

    def _get_pipeline(self, lang_code: str) -> object:
        """Return cached KPipeline for lang_code; load once per language."""
        if lang_code not in self._pipelines:
            try:
                from kokoro import KPipeline
            except ImportError as e:
                raise RuntimeError(
                    "Kokoro TTS requires: uv sync --extra tts_kokoro (pip install kokoro)"
                ) from e
            self._pipelines[lang_code] = KPipeline(lang_code=lang_code)
        return self._pipelines[lang_code]

    def synthesize(
        self,
        text: str,
        *,
        output_path: str | Path | None = None,
        voice: str | None = None,
        speed: float | None = None,
        **kwargs: object,
    ) -> bytes:
        voice_name = voice or (kwargs.get("voice") or "af_heart")
        lang_code = kwargs.get("lang_code") or (voice_name[0] if voice_name else "a")
        speed_val = speed if speed is not None else (kwargs.get("speed") or 1.0)
        split_pattern = kwargs.get("split_pattern") or r"\n+"

        pipeline = self._get_pipeline(lang_code)
        generator = pipeline(text, voice=voice_name, speed=speed_val, split_pattern=split_pattern)
        all_audio: list[np.ndarray] = []
        for _gs, _ps, audio in generator:
            all_audio.append(_to_numpy(audio))

        if not all_audio:
            raise RuntimeError("Kokoro produced no audio")
        combined = np.concatenate(all_audio)
        sample_rate = 24000

        try:
            import soundfile as sf
        except ImportError as e:
            raise RuntimeError(
                "Kokoro backend needs soundfile to write WAV (uv sync --extra voice_tx or tts_kokoro)"
            ) from e

        buf = io.BytesIO()
        sf.write(buf, combined, sample_rate, format="WAV")
        data = buf.getvalue()

        if output_path:
            Path(output_path).write_bytes(data)
        return data
