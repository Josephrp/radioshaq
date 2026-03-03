"""Effective callsign whitelist: config allowed_callsigns merged with DB registered_callsigns."""

from __future__ import annotations

from typing import Any

from radioshaq.config.schema import RadioConfig


def _normalize(callsign: str | None) -> str | None:
    if not callsign or not isinstance(callsign, str):
        return None
    s = callsign.strip().upper()
    return s if s else None


async def get_effective_allowed_callsigns(
    db: Any,
    config: RadioConfig,
) -> set[str]:
    """
    Return the set of callsigns that are allowed (config + DB registry).
    If config.allowed_callsigns is set, start from that list (normalized);
    otherwise start empty. Then add all DB-registered callsigns if db is available.
    """
    allowed: set[str] = set()
    if config.allowed_callsigns:
        allowed = {c.strip().upper() for c in config.allowed_callsigns if c and isinstance(c, str)}
    if db is not None and hasattr(db, "list_registered_callsigns"):
        try:
            registered = await db.list_registered_callsigns()
            for r in registered:
                cs = r.get("callsign")
                if cs:
                    allowed.add(str(cs).strip().upper())
        except Exception:
            pass
    return allowed


def is_callsign_allowed(
    callsign: str | None,
    allowed: set[str],
    registry_required: bool,
) -> bool:
    """
    Return True if the callsign is allowed.
    - If callsign is None or empty, return False.
    - If allowed set is non-empty and callsign not in it, return False.
    - If registry_required is True and allowed is empty, return False (no one allowed).
    - Otherwise return True.
    """
    normalized = _normalize(callsign)
    if not normalized:
        return False
    if allowed and normalized not in allowed:
        return False
    if registry_required and not allowed:
        return False
    return True
