"""Text-to-speech using ElevenLabs API."""

from __future__ import annotations

import os
from pathlib import Path


def text_to_speech_elevenlabs(
    text: str,
    voice_id: str = "21m00Tcm4TlvDq8ikWAM",  # Rachel - default voice
    api_key: str | None = None,
    model_id: str = "eleven_multilingual_v2",
    output_format: str = "mp3_44100_128",
    output_path: str | Path | None = None,
) -> bytes:
    """
    Convert text to speech using ElevenLabs API.

    Args:
        text: Text to speak.
        voice_id: ElevenLabs voice ID (default: Rachel). List voices: GET /v1/voices.
        api_key: ElevenLabs API key. Defaults to env ELEVENLABS_API_KEY.
        model_id: Model (eleven_multilingual_v2, eleven_turbo_v2_5, eleven_flash_v2_5, etc.).
        output_format: e.g. mp3_44100_128, wav_22050.
        output_path: If set, write audio bytes to this file.

    Returns:
        Audio bytes (e.g. MP3).

    Requires: httpx (already in shakods deps).
    """
    import httpx

    key = api_key or os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError(
            "Set ELEVENLABS_API_KEY or pass api_key= to use ElevenLabs TTS."
        )

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": model_id,
    }
    params = {"output_format": output_format}

    with httpx.Client(timeout=60.0) as client:
        r = client.post(url, json=payload, headers=headers, params=params)
        r.raise_for_status()
        data = r.content

    if output_path:
        Path(output_path).write_bytes(data)
    return data
