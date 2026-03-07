"""Audio ASR (Voxtral, Whisper, Scribe), TTS (ElevenLabs, Kokoro), capture and stream processing."""

from __future__ import annotations

__all__ = [
    "transcribe_audio_voxtral",
    "text_to_speech_elevenlabs",
    "synthesize_speech",
    "transcribe_audio",
    "AudioCaptureService",
    "AudioStreamProcessor",
    "ProcessedSegment",
]


def __getattr__(name: str):
    if name == "transcribe_audio_voxtral":
        from radioshaq.audio.asr import transcribe_audio_voxtral
        return transcribe_audio_voxtral
    if name == "text_to_speech_elevenlabs":
        from radioshaq.audio.tts import text_to_speech_elevenlabs
        return text_to_speech_elevenlabs
    if name == "synthesize_speech":
        from radioshaq.audio.tts_plugin import synthesize_speech
        return synthesize_speech
    if name == "transcribe_audio":
        from radioshaq.audio.asr_plugin import transcribe_audio
        return transcribe_audio
    if name == "AudioCaptureService":
        from radioshaq.audio.capture import AudioCaptureService
        return AudioCaptureService
    if name == "AudioStreamProcessor":
        from radioshaq.audio.stream_processor import AudioStreamProcessor
        return AudioStreamProcessor
    if name == "ProcessedSegment":
        from radioshaq.audio.stream_processor import ProcessedSegment
        return ProcessedSegment
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
