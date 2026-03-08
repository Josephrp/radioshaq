"""ASR: Voxtral, Whisper, Scribe (via asr_plugin)."""

from __future__ import annotations

from pathlib import Path

from radioshaq.audio.asr_plugin import transcribe_audio

VOXTRAL_ASR_HF_MODEL_ID = "shakods/voxtral-asr-en"


def transcribe_audio_voxtral(
    audio_path: str | Path,
    model_id: str = VOXTRAL_ASR_HF_MODEL_ID,
    language: str = "en",
) -> str:
    """
    Transcribe audio file using Voxtral ASR (via ASR plugin).

    Requires: uv sync --extra audio.
    """
    return transcribe_audio(audio_path, model_id=model_id, language=language)
