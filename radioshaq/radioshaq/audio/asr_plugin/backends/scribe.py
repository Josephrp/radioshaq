"""ElevenLabs Scribe API ASR backend. Requires ELEVENLABS_API_KEY."""

from __future__ import annotations

import logging
import os
from pathlib import Path


logger = logging.getLogger(__name__)


class ScribeASRBackend:
    """Transcribe using ElevenLabs Scribe (Speech-to-Text) API.

    Optionally runs ElevenLabs Voice Isolator (audio-isolation) before STT when
    use_voice_isolator=True is passed or RADIOSHAQ_AUDIO__ELEVEN_VOICE_ISOLATOR_ENABLED
    (or ELEVEN_VOICE_ISOLATOR_ENABLED) is set to a truthy value.
    """

    def _voice_isolator_enabled(self, kwargs: dict[str, object]) -> bool:
        """Return True when ElevenLabs Voice Isolator should be used."""
        flag = kwargs.get("use_voice_isolator")
        if isinstance(flag, bool):
            return flag
        env_val = os.environ.get("RADIOSHAQ_AUDIO__ELEVEN_VOICE_ISOLATOR_ENABLED") or os.environ.get(
            "ELEVEN_VOICE_ISOLATOR_ENABLED"
        )
        if not env_val:
            return False
        return env_val.strip().lower() in ("1", "true", "yes", "on")

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

        # kwargs is typed as object variadically; cast to dict internally.
        kw = dict(kwargs)  # type: ignore[arg-type]

        api_key = kw.get("api_key") or os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Set ELEVENLABS_API_KEY or pass api_key= to use Scribe ASR."
            )

        # Use scribe_model_id so the plugin does not send the routing key "scribe" as the API model.
        api_model_id = kw.get("scribe_model_id") or "scribe_v2"
        stt_url = "https://api.elevenlabs.io/v1/speech-to-text"
        headers = {"xi-api-key": api_key}

        # Optional: run ElevenLabs Voice Isolator (audio-isolation) first to denoise.
        cleaned_audio: bytes | None = None
        if self._voice_isolator_enabled(kw):
            iso_url = "https://api.elevenlabs.io/v1/audio-isolation"
            try:
                raw_bytes = path.read_bytes()
                iso_files = {"audio": (path.name, raw_bytes, "audio/wav")}
                iso_data = {"file_format": "other"}
                with httpx.Client(timeout=120.0) as client:
                    iso_resp = client.post(
                        iso_url,
                        files=iso_files,
                        data=iso_data,
                        headers=headers,
                    )
                    iso_resp.raise_for_status()
                    cleaned_audio = iso_resp.content
                    logger.debug(
                        "ElevenLabs Voice Isolator applied for %s (bytes=%s)",
                        path,
                        len(cleaned_audio),
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Voice Isolator failed for %s, using raw audio: %s",
                    path,
                    e,
                )
                cleaned_audio = None

        data = {"model_id": api_model_id}
        if language and language.lower() != "auto":
            data["language_code"] = language

        with httpx.Client(timeout=120.0) as client:
            if cleaned_audio is not None:
                files = {"file": (path.name, cleaned_audio, "audio/wav")}
            else:
                f = path.open("rb")
                try:
                    files = {"file": (path.name, f, "audio/wav")}
                except Exception:
                    f.close()
                    raise
            try:
                r = client.post(stt_url, files=files, data=data, headers=headers)
                r.raise_for_status()
                out = r.json()
            finally:
                # Close file handle if we opened one (cleaned_audio path does not create f)
                if "f" in locals() and not f.closed:
                    f.close()

        text = out.get("text") if isinstance(out, dict) else None
        return (text or "").strip()
