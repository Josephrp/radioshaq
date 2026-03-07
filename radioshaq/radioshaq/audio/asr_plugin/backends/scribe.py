"""ElevenLabs Scribe API ASR backend. Requires ELEVENLABS_API_KEY."""

from __future__ import annotations

import os
from pathlib import Path


class ScribeASRBackend:
    """Transcribe using ElevenLabs Scribe (Speech-to-Text) API."""

    def transcribe(
        self,
        audio_path: str | Path,
        *,
        language: str | None = None,
        **kwargs: object,
    ) -> str:
        import httpx

        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(str(audio_path))

        api_key = kwargs.get("api_key") or os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Set ELEVENLABS_API_KEY or pass api_key= to use Scribe ASR."
            )

        # Use scribe_model_id so the plugin does not send the routing key "scribe" as the API model.
        api_model_id = kwargs.get("scribe_model_id") or "scribe_v2"
        url = "https://api.elevenlabs.io/v1/speech-to-text"
        headers = {"xi-api-key": api_key}
        with path.open("rb") as f:
            files = {"file": (path.name, f, "audio/wav")}
            data = {"model_id": api_model_id}
            if language and language.lower() != "auto":
                data["language_code"] = language
            with httpx.Client(timeout=120.0) as client:
                r = client.post(url, files=files, data=data, headers=headers)
                r.raise_for_status()
                out = r.json()

        text = out.get("text") if isinstance(out, dict) else None
        return (text or "").strip()
