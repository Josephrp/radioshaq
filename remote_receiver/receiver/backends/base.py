"""SDR backend protocol: one interface, multiple backends (RTL-SDR, HackRF)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from receiver.radio_interface import SignalSample

__all__ = ["SDRBackend"]


class SDRBackend(ABC):
    """Abstract base for SDR backends. Implement initialize, set_frequency, receive, close."""

    @abstractmethod
    async def initialize(self) -> None:
        """Open device and set defaults."""
        ...

    @abstractmethod
    async def set_frequency(self, frequency_hz: float) -> None:
        """Tune to frequency in Hz."""
        ...

    @abstractmethod
    async def receive(self, duration_seconds: float) -> AsyncIterator[SignalSample]:
        """Stream signal samples for duration. Yield real I/Q-derived strength when possible."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release device."""
        ...
