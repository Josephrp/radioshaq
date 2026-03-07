"""Text-to-speech: ElevenLabs API and Kokoro (via tts_plugin)."""

from __future__ import annotations

from pathlib import Path

from radioshaq.audio.tts_plugin import synthesize_speech


def text_to_speech_elevenlabs(
    text: str,
    voice_id: str = "21m00Tcm4TlvDq8ikWAM",  # Rachel - default voice
    api_key: str | None = None,
    model_id: str = "eleven_multilingual_v2",
    output_format: str = "mp3_44100_128",
    output_path: str | Path | None = None,
) -> bytes:
    """
    Convert text to speech using ElevenLabs API (via TTS plugin).

    Args:
        text: Text to speak.
        voice_id: ElevenLabs voice ID (default: Rachel). List voices: GET /v1/voices.
        api_key: ElevenLabs API key. Defaults to env ELEVENLABS_API_KEY.
        model_id: Model (eleven_multilingual_v2, eleven_turbo_v2_5, eleven_flash_v2_5, etc.).
        output_format: e.g. mp3_44100_128, wav_22050.
        output_path: If set, write audio bytes to this file.

    Returns:
        Audio bytes (e.g. MP3).
    """
    return synthesize_speech(
        text,
        "elevenlabs",
        output_path=output_path,
        voice=voice_id,
        api_key=api_key,
        model_id=model_id,
        output_format=output_format,
    )
