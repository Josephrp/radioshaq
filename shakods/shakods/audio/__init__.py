"""Audio ASR (Voxtral), TTS (ElevenLabs), capture and stream processing."""

from __future__ import annotations

__all__ = [
    "transcribe_audio_voxtral",
    "text_to_speech_elevenlabs",
    "AudioCaptureService",
    "AudioStreamProcessor",
    "ProcessedSegment",
]


def __getattr__(name: str):
    if name == "transcribe_audio_voxtral":
        from shakods.audio.asr import transcribe_audio_voxtral
        return transcribe_audio_voxtral
    if name == "text_to_speech_elevenlabs":
        from shakods.audio.tts import text_to_speech_elevenlabs
        return text_to_speech_elevenlabs
    if name == "AudioCaptureService":
        from shakods.audio.capture import AudioCaptureService
        return AudioCaptureService
    if name == "AudioStreamProcessor":
        from shakods.audio.stream_processor import AudioStreamProcessor
        return AudioStreamProcessor
    if name == "ProcessedSegment":
        from shakods.audio.stream_processor import ProcessedSegment
        return ProcessedSegment
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
