"""SDR radio interface (RTL-SDR when pyrtlsdr available)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from loguru import logger


@dataclass
class SignalSample:
    """A single signal sample or decoded result."""

    timestamp: datetime
    frequency_hz: float
    strength_db: float
    decoded_data: str | None = None
    raw_data: bytes | None = None
    mode: str = ""

    @property
    def is_interesting(self) -> bool:
        """True if signal is above a simple threshold."""
        return self.strength_db >= -90.0


class SDRInterface:
    """
    SDR interface for receiving. Uses pyrtlsdr when available;
    otherwise provides a stub for testing.
    """

    def __init__(self, device_index: int = 0, sample_rate: int = 2_400_000):
        self.device_index = device_index
        self.sample_rate = sample_rate
        self._frequency_hz: float = 0.0
        self._rtl = None

    async def initialize(self) -> None:
        """Initialize SDR hardware."""
        try:
            import rtlsdr
            self._rtl = rtlsdr.RtlSdr(self.device_index)
            self._rtl.sample_rate = self.sample_rate
            logger.info("RTL-SDR initialized")
        except ImportError:
            logger.warning("pyrtlsdr not installed; using stub SDR")
        except Exception as e:
            logger.warning("RTL-SDR init failed: %s; using stub", e)

    async def set_frequency(self, frequency_hz: float) -> None:
        """Tune to frequency in Hz."""
        self._frequency_hz = frequency_hz
        if self._rtl:
            self._rtl.center_freq = int(frequency_hz)

    async def receive(
        self, duration_seconds: float
    ) -> AsyncIterator[SignalSample]:
        """Stream signal samples for duration (stub yields placeholder)."""
        loop = asyncio.get_running_loop()
        end = loop.time() + duration_seconds
        while loop.time() < end:
            yield SignalSample(
                timestamp=datetime.now(timezone.utc),
                frequency_hz=self._frequency_hz,
                strength_db=-100.0,
                decoded_data=None,
            )
            await asyncio.sleep(0.1)

    async def scan_frequency(
        self,
        frequency_hz: float,
        bandwidth_hz: float,
        duration_seconds: float,
    ) -> list[SignalSample]:
        """Scan a frequency and return list of samples (stub)."""
        await self.set_frequency(frequency_hz)
        samples: list[SignalSample] = []
        async for s in self.receive(duration_seconds):
            samples.append(s)
        return samples
