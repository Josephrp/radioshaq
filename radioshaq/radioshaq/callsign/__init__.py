"""Callsign registry: repository abstraction for whitelisted (registered) callsigns with access to gated services."""

from radioshaq.callsign.repository import (
    CallsignRegistryRepository,
    CallsignRegistryRepositoryImpl,
    get_callsign_repository,
)

__all__ = [
    "CallsignRegistryRepository",
    "CallsignRegistryRepositoryImpl",
    "get_callsign_repository",
]
