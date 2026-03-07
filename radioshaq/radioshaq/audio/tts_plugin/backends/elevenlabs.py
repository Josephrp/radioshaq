"""ElevenLabs API TTS backend."""

from __future__ import annotations

import os
from pathlib import Path


class ElevenLabsTTSBackend:
    """TTS via ElevenLabs API. Requires ELEVENLABS_API_KEY."""

    def synthesize(
        self,
        text: str,
        *,
        output_path: str | Path | None = None,
        voice: str | None = None,
        speed: float | None = None,
        **kwargs: object,
    ) -> bytes:
        import httpx

        voice_id = (voice if voice is not None else kwargs.get("voice_id")) or "21m00Tcm4TlvDq8ikWAM"
        model_id = kwargs.get("model_id") or "eleven_multilingual_v2"
        output_format = kwargs.get("output_format") or "mp3_44100_128"
        api_key = kwargs.get("api_key") or os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Set ELEVENLABS_API_KEY or pass api_key= to use ElevenLabs TTS."
            )

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        }
        payload = {"text": text, "model_id": model_id}
        params = {"output_format": output_format}

        with httpx.Client(timeout=60.0) as client:
            r = client.post(url, json=payload, headers=headers, params=params)
            r.raise_for_status()
            data = r.content

        if output_path:
            Path(output_path).write_bytes(data)
        return data
