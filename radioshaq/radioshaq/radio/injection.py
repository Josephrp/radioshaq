"""In-memory injection queue for demo and testing: simulate received radio messages.

Allows user scripts or the API to inject text (and optional audio path) so that
receivers can "hear" messages without real hardware or FLDIGI. Used for:
- Demo on two local machines + one remote with user injection script
- Band-translation scenario (inject on one band, relay to another)

Re-put semantics: when a consumer (e.g. radio_rx with band filter) gets a message
that does not match (e.g. wrong band), it may call put_back_nowait(msg). If the
queue is full, the message is dropped and a warning is logged to avoid deadlock.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class InjectedMessage:
    """A single injected receive (simulated or from real audio pipeline)."""

    text: str
    band: str | None = None
    frequency_hz: float = 0.0
    mode: str = "PSK31"
    source_callsign: str | None = None
    destination_callsign: str | None = None
    audio_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class InMemoryInjectionQueue:
    """
    Async queue of injected messages for RX path.

    - API or user script pushes via inject_message().
    - radio_rx or digital_modes wrapper pops via receive_injected(timeout=...).
    """

    def __init__(self, maxsize: int = 100):
        self._queue: asyncio.Queue[InjectedMessage] = asyncio.Queue(maxsize=maxsize)

    def inject_message(
        self,
        text: str,
        band: str | None = None,
        frequency_hz: float = 0.0,
        mode: str = "PSK31",
        source_callsign: str | None = None,
        destination_callsign: str | None = None,
        audio_path: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Add a message to the RX injection queue (non-blocking)."""
        msg = InjectedMessage(
            text=text,
            band=band,
            frequency_hz=frequency_hz,
            mode=mode,
            source_callsign=source_callsign,
            destination_callsign=destination_callsign,
            audio_path=audio_path,
            metadata=metadata or {},
        )
        try:
            self._queue.put_nowait(msg)
            logger.debug("Injected message for RX: band=%s freq=%s text=%s", band, frequency_hz, text[:50])
        except asyncio.QueueFull:
            logger.warning("Injection queue full, dropping message")

    async def receive_injected(self, timeout: float = 10.0) -> InjectedMessage | None:
        """Wait for one injected message (for use when FLDIGI/hardware not available)."""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def receive_injected_nowait(self) -> InjectedMessage | None:
        """Get one injected message if available, else None."""
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def put_back_nowait(self, msg: InjectedMessage) -> bool:
        """Re-put a message (e.g. after band mismatch). Returns True if put, False if queue full (message dropped)."""
        try:
            self._queue.put_nowait(msg)
            return True
        except asyncio.QueueFull:
            logger.warning("Injection queue full on re-put, dropping message (band=%s)", getattr(msg, "band", None))
            return False

    def qsize(self) -> int:
        return self._queue.qsize()


# Module-level singleton for use by API and agents when not using FLDIGI
_injection_queue: InMemoryInjectionQueue | None = None


def get_injection_queue() -> InMemoryInjectionQueue:
    """Return the global injection queue (create if needed)."""
    global _injection_queue
    if _injection_queue is None:
        _injection_queue = InMemoryInjectionQueue()
    return _injection_queue
