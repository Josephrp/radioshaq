"""TTS backends: ElevenLabs (API), Kokoro (local)."""

from radioshaq.audio.tts_plugin.backends.elevenlabs import ElevenLabsTTSBackend

__all__ = ["ElevenLabsTTSBackend"]

try:
    from radioshaq.audio.tts_plugin.backends.kokoro import KokoroTTSBackend
    __all__ = list(__all__) + ["KokoroTTSBackend"]
except ImportError:
    pass
