"""Audio ASR (Voxtral) and TTS (ElevenLabs) for demo and injection."""

from __future__ import annotations

__all__ = ["transcribe_audio_voxtral", "text_to_speech_elevenlabs"]


def __getattr__(name: str):
    if name == "transcribe_audio_voxtral":
        from shakods.audio.asr import transcribe_audio_voxtral
        return transcribe_audio_voxtral
    if name == "text_to_speech_elevenlabs":
        from shakods.audio.tts import text_to_speech_elevenlabs
        return text_to_speech_elevenlabs
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
