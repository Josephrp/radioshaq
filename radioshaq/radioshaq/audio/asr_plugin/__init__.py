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


def _is_voxtral_like_model_id(model_id: str) -> bool:
    """True if model_id looks like a Voxtral HF repo (route to voxtral backend)."""
    if not model_id or not model_id.strip():
        return False
    s = model_id.strip().lower()
    return s == "voxtral" or "voxtral" in s or s.startswith("shakods/") or s.startswith("mistralai/voxtral")


def transcribe_audio(
    audio_path: str | Path,
    model_id: str = "voxtral",
    *,
    language: str | None = None,
    **kwargs: object,
) -> str:
    """Transcribe audio using the configured backend. Raises if backend not found or transcription fails."""
    backend_key = (
        model_id
        if model_id in _backends
        else ("voxtral" if _backends.get("voxtral") and _is_voxtral_like_model_id(model_id) else model_id)
    )
    backend = _backends.get(backend_key)
    if backend is None:
        raise RuntimeError(
            f"ASR backend {model_id!r} not available. "
            "For voxtral/whisper run: uv sync --extra audio. For scribe set ELEVENLABS_API_KEY."
        )
    return backend.transcribe(
        audio_path, language=language, model_id=model_id, **kwargs
    )


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
