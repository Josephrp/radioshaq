"""Callsign registry repository: abstraction over who is whitelisted (registered for gated services)."""

from __future__ import annotations

from typing import Any, Protocol


class CallsignRegistryRepository(Protocol):
    """Protocol for callsign registry access (list, register, unregister, is_registered)."""

    async def list_registered(self) -> list[dict[str, Any]]:
        """List all registered callsigns. Order and shape are implementation-defined."""
        ...

    async def register(self, callsign: str, source: str = "api") -> int:
        """Register a callsign. Returns id (new or existing). Normalizes to upper."""
        ...

    async def unregister(self, callsign: str) -> bool:
        """Remove a callsign from the registry. Returns True if one was removed."""
        ...

    async def is_registered(self, callsign: str) -> bool:
        """Return True if the callsign is in the registry."""
        ...


class CallsignRegistryRepositoryImpl:
    """Implementation backed by PostGISManager (or any db with the same method names)."""

    def __init__(self, db: Any) -> None:
        self._db = db

    async def list_registered(self) -> list[dict[str, Any]]:
        return await self._db.list_registered_callsigns()

    async def register(self, callsign: str, source: str = "api") -> int:
        normalized = (callsign or "").strip().upper()
        return await self._db.register_callsign(normalized, source)

    async def unregister(self, callsign: str) -> bool:
        normalized = (callsign or "").strip().upper()
        return await self._db.unregister_callsign(normalized)

    async def is_registered(self, callsign: str) -> bool:
        normalized = (callsign or "").strip().upper()
        return await self._db.is_callsign_registered(normalized)


def get_callsign_repository(db: Any) -> CallsignRegistryRepository | None:
    """Return a CallsignRegistryRepository if db has the required methods, else None."""
    if db is None:
        return None
    for method in ("list_registered_callsigns", "register_callsign", "unregister_callsign", "is_callsign_registered"):
        if not callable(getattr(db, method, None)):
            return None
    return CallsignRegistryRepositoryImpl(db)
