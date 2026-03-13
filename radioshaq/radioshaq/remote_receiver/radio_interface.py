"""SDR radio interface: backend abstraction and factory from env."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, AsyncIterator

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


def create_sdr_from_env(
    *,
    device_manager: Any | None = None,
    broker: Any | None = None,
) -> "SDRInterface":
    """
    Build SDR from environment. SDR_TYPE=rtlsdr (default) or hackrf.
    RTL-SDR: RTLSDR_INDEX (default 0).
    HackRF: HACKRF_INDEX (default 0), HACKRF_SERIAL (optional).
    """
    sdr_type = os.environ.get("SDR_TYPE", "rtlsdr").strip().lower()
    if sdr_type == "hackrf":
        from radioshaq.remote_receiver.backends.hackrf_backend import HackRFBackend

        index = int(os.environ.get("HACKRF_INDEX", "0"))
        serial = os.environ.get("HACKRF_SERIAL") or None
        sample_rate = int(os.environ.get("HACKRF_SAMPLE_RATE", "10000000"))
        backend = HackRFBackend(
            device_index=index,
            serial_number=serial,
            sample_rate=sample_rate,
            device_manager=device_manager,
        )
        # Broker (when provided) is used for RX/TX scheduling flags only.
        if broker is not None:
            setattr(backend, "_broker", broker)
    else:
        from radioshaq.remote_receiver.backends.rtlsdr_backend import RtlSdrBackend

        index = int(os.environ.get("RTLSDR_INDEX", "0"))
        sample_rate = int(os.environ.get("RTLSDR_SAMPLE_RATE", "2400000"))
        backend = RtlSdrBackend(device_index=index, sample_rate=sample_rate)
    return SDRInterface(backend=backend)


class SDRInterface:
    """
    SDR interface for receiving. Wraps an SDRBackend (RTL-SDR or HackRF).
    Use create_sdr_from_env() to build from environment.
    """

    def __init__(
        self,
        backend: SDRBackend | None = None,
        device_index: int = 0,
        sample_rate: int = 2_400_000,
    ):
        if backend is not None:
            self._backend = backend
        else:
            from radioshaq.remote_receiver.backends.rtlsdr_backend import RtlSdrBackend

            self._backend = RtlSdrBackend(device_index=device_index, sample_rate=sample_rate)

    async def initialize(self) -> None:
        """Initialize SDR hardware."""
        await self._backend.initialize()

    async def set_frequency(self, frequency_hz: float) -> None:
        """Tune to frequency in Hz."""
        await self._backend.set_frequency(frequency_hz)

    async def configure(
        self,
        *,
        mode: str | None = None,
        audio_rate_hz: int | None = None,
        bfo_hz: float | None = None,
    ) -> None:
        """Configure backend demod settings (if supported)."""
        if hasattr(self._backend, "configure"):
            await self._backend.configure(mode=mode, audio_rate_hz=audio_rate_hz, bfo_hz=bfo_hz)

    async def receive(self, duration_seconds: float) -> AsyncIterator[SignalSample]:
        """Stream signal samples for duration."""
        async for sample in self._backend.receive(duration_seconds):
            yield sample

    async def scan_frequency(
        self,
        frequency_hz: float,
        bandwidth_hz: float,
        duration_seconds: float,
    ) -> list[SignalSample]:
        """Scan a frequency and return list of samples."""
        await self.set_frequency(frequency_hz)
        samples: list[SignalSample] = []
        async for s in self.receive(duration_seconds):
            samples.append(s)
        return samples

    async def close(self) -> None:
        """Release SDR (call on shutdown)."""
        await self._backend.close()


if TYPE_CHECKING:
    from radioshaq.remote_receiver.backends.base import SDRBackend
