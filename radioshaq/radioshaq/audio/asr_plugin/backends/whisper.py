"""Whisper ASR backend. Requires: pip install openai-whisper."""

from __future__ import annotations

from pathlib import Path


class WhisperASRBackend:
    """Transcribe using OpenAI Whisper (local)."""

    def __init__(self) -> None:
        self._model: object | None = None

    def _get_model(self) -> object:
        if self._model is None:
            try:
                import whisper
                self._model = whisper.load_model("base")
            except ImportError as e:
                raise RuntimeError(
                    "Whisper ASR requires: pip install openai-whisper"
                ) from e
        return self._model

    def transcribe(
        self,
        audio_path: str | Path,
        *,
        language: str | None = None,
        **kwargs: object,
    ) -> str:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(str(audio_path))
        model = self._get_model()
        lang_arg = language if language and str(language).strip().lower() != "auto" else None
        result = model.transcribe(str(path), fp16=False, language=lang_arg)
        return (result.get("text") or "").strip()
