"""Shared constants for RadioShaq (e.g. ASR language support)."""

from __future__ import annotations

# ASR (Voxtral) languages supported for UI and validation (en, fr, es)
ASR_SUPPORTED_LANGUAGE_CODES: tuple[str, ...] = ("en", "fr", "es")
ASR_LANGUAGE_AUTO = "auto"
# All valid asr_language values: codes + auto for detection
ASR_LANGUAGE_VALUES: tuple[str, ...] = (*ASR_SUPPORTED_LANGUAGE_CODES, ASR_LANGUAGE_AUTO)
