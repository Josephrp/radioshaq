"""ASR backend protocol: pluggable speech-to-text providers (Voxtral, Whisper, Scribe)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ASRBackend(Protocol):
    """Provides speech-to-text transcription. Implementations: Voxtral, Whisper (local), Scribe (API)."""

    def transcribe(
        self,
        audio_path: str | Path,
        *,
        language: str | None = None,
        **kwargs: object,
    ) -> str:
        """Transcribe audio file to text.

        Args:
            audio_path: Path to audio file (WAV or format supported by backend).
            language: Optional language hint (e.g. en, fr, es, auto).
            **kwargs: Backend-specific options.

        Returns:
            Transcribed text.
        """
        ...
