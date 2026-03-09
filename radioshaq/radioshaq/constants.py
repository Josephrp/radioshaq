"""Shared constants for RadioShaq (e.g. ASR language support)."""

from __future__ import annotations

import re

# E.164 phone validation: optional +, 10–15 digits (shared across emergency, relay, callsigns)
E164_PATTERN: re.Pattern[str] = re.compile(r"^\+?[0-9]{10,15}$")

# Regions that require explicit consent for notify-on-relay (§8.1, §8.3)
EXPLICIT_CONSENT_REGIONS: frozenset[str] = frozenset(
    ("CEPT", "FR", "UK", "ES", "BE", "CH", "LU", "MC", "ZA")
)

# ASR (Voxtral) languages supported for UI and validation (en, fr, es)
ASR_SUPPORTED_LANGUAGE_CODES: tuple[str, ...] = ("en", "fr", "es")
ASR_LANGUAGE_AUTO = "auto"
# All valid asr_language values: codes + auto for detection
ASR_LANGUAGE_VALUES: tuple[str, ...] = (*ASR_SUPPORTED_LANGUAGE_CODES, ASR_LANGUAGE_AUTO)
