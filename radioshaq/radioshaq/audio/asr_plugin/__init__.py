"""ASR plugin: registry of backends (Voxtral, Whisper, Scribe) and transcribe_audio entry point."""

from __future__ import annotations

from pathlib import Path

from radioshaq.audio.asr_plugin.base import ASRBackend

_backends: dict[str, ASRBackend] = {}


def register_asr_backend(model_id: str, backend: ASRBackend) -> None:
    """Register an ASR backend (e.g. 'voxtral', 'whisper', 'scribe')."""
    _backends[model_id] = backend


def get_asr_backend(model_id: str) -> ASRBackend | None:
    """Return the backend for the given model_id, or None if not registered."""
    return _backends.get(model_id)


def transcribe_audio(
    audio_path: str | Path,
    model_id: str = "voxtral",
    *,
    language: str | None = None,
    **kwargs: object,
) -> str:
    """Transcribe audio using the configured backend. Raises if backend not found or transcription fails."""
    backend = _backends.get(model_id)
    if backend is None:
        raise RuntimeError(
            f"ASR backend {model_id!r} not available. "
            "For voxtral/whisper run: uv sync --extra audio. For scribe set ELEVENLABS_API_KEY."
        )
    return backend.transcribe(audio_path, language=language, **kwargs)


def _register_backends() -> None:
    try:
        from radioshaq.audio.asr_plugin.backends.voxtral import VoxtralASRBackend
        register_asr_backend("voxtral", VoxtralASRBackend())
    except ImportError:
        pass
    try:
        from radioshaq.audio.asr_plugin.backends.whisper import WhisperASRBackend
        register_asr_backend("whisper", WhisperASRBackend())
    except ImportError:
        pass
    from radioshaq.audio.asr_plugin.backends.scribe import ScribeASRBackend
    register_asr_backend("scribe", ScribeASRBackend())


_register_backends()

__all__ = [
    "ASRBackend",
    "get_asr_backend",
    "register_asr_backend",
    "transcribe_audio",
]
