"""ASR backends: Voxtral, Whisper (local), Scribe (ElevenLabs API)."""

from radioshaq.audio.asr_plugin.backends.scribe import ScribeASRBackend

__all__ = ["ScribeASRBackend"]

try:
    from radioshaq.audio.asr_plugin.backends.voxtral import VoxtralASRBackend
    __all__ = list(__all__) + ["VoxtralASRBackend"]
except ImportError:
    pass
try:
    from radioshaq.audio.asr_plugin.backends.whisper import WhisperASRBackend
    __all__ = list(__all__) + ["WhisperASRBackend"]
except ImportError:
    pass
