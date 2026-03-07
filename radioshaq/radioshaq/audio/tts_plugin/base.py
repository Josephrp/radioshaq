"""TTS backend protocol: pluggable text-to-speech providers (ElevenLabs, Kokoro)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class TTSBackend(Protocol):
    """Provides text-to-speech synthesis. Implementations: ElevenLabs (API), Kokoro (local)."""

    def synthesize(
        self,
        text: str,
        *,
        output_path: str | Path | None = None,
        voice: str | None = None,
        speed: float | None = None,
        **kwargs: object,
    ) -> bytes:
        """Synthesize text to audio.

        Args:
            text: Input text to speak.
            output_path: If set, write audio bytes to this file.
            voice: Provider-specific voice id or name (e.g. ElevenLabs voice_id, Kokoro voice name).
            speed: Speech rate (provider-specific; e.g. Kokoro 0.5–2.0).
            **kwargs: Provider-specific options (e.g. model_id, lang_code, api_key).

        Returns:
            Audio bytes (format is provider-specific: e.g. MP3 for ElevenLabs, WAV for Kokoro).
        """
        ...
