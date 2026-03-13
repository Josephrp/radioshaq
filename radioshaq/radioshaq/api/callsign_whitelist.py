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

    Semantics:
    - If callsign is None or empty, return False.
    - When registry_required is True:
        * If allowed is empty, no one is allowed (False).
        * If allowed is non-empty, callsign must be in the set.
    - When registry_required is False:
        * Whitelist is advisory only; any non-empty callsign is allowed.
    """
    normalized = _normalize(callsign)
    if not normalized:
        return False
    if registry_required:
        if not allowed:
            return False
        return normalized in allowed
    # Registry not required: accept any normalized callsign regardless of allowed set contents.
    return True
