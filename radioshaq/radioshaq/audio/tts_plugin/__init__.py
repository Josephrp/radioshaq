"""TTS plugin: registry of backends (ElevenLabs, Kokoro) and synthesize_speech entry point."""

from __future__ import annotations

from pathlib import Path

from radioshaq.audio.tts_plugin.base import TTSBackend

_backends: dict[str, TTSBackend] = {}


def register_tts_backend(provider_id: str, backend: TTSBackend) -> None:
    """Register a TTS backend (e.g. 'elevenlabs', 'kokoro')."""
    _backends[provider_id] = backend


def get_tts_backend(provider_id: str) -> TTSBackend | None:
    """Return the backend for the given provider_id, or None if not registered."""
    return _backends.get(provider_id)


def synthesize_speech(
    text: str,
    provider_id: str,
    *,
    output_path: str | Path | None = None,
    voice: str | None = None,
    speed: float | None = None,
    **kwargs: object,
) -> bytes:
    """Synthesize text using the configured provider. Raises if provider not found or synthesis fails."""
    backend = _backends.get(provider_id)
    if backend is None:
        raise RuntimeError(
            f"TTS provider {provider_id!r} not available. "
            "For elevenlabs set ELEVENLABS_API_KEY. For kokoro run: uv sync --extra tts_kokoro"
        )
    return backend.synthesize(
        text,
        output_path=output_path,
        voice=voice,
        speed=speed,
        **kwargs,
    )


# Register built-in backends
def _register_backends() -> None:
    from radioshaq.audio.tts_plugin.backends.elevenlabs import ElevenLabsTTSBackend
    register_tts_backend("elevenlabs", ElevenLabsTTSBackend())
    try:
        from radioshaq.audio.tts_plugin.backends.kokoro import KokoroTTSBackend
        register_tts_backend("kokoro", KokoroTTSBackend())
    except ImportError:
        pass  # kokoro optional (uv sync --extra tts_kokoro)


_register_backends()

__all__ = [
    "TTSBackend",
    "get_tts_backend",
    "register_tts_backend",
    "synthesize_speech",
]
