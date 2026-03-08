"""Phone number normalization (E.164)."""

from __future__ import annotations

import re


def normalize_e164(phone: str) -> str:
    """Normalize to E.164: optional +, digits only (10–15 chars)."""
    digits = re.sub(r"\D", "", (phone or "").strip())
    return "+" + digits if digits else ""
