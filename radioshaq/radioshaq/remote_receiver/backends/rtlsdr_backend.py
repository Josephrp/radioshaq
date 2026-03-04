"""RTL-SDR backend with real I/Q streaming."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import AsyncIterator

import numpy as np
from loguru import logger

from radioshaq.remote_receiver.backends.base import SDRBackend
from radioshaq.remote_receiver.radio_interface import SignalSample


class RtlSdrBackend(SDRBackend):
    """RTL-SDR backend: real I/Q via pyrtlsdr read_samples, power -> dB."""

    def __init__(self, device_index: int = 0, sample_rate: int = 2_400_000):
        self.device_index = device_index
        self.sample_rate = sample_rate
        self._frequency_hz: float = 0.0
        self._rtl = None

    async def initialize(self) -> None:
        """Open RTL-SDR device."""
        try:
            import rtlsdr

            self._rtl = rtlsdr.RtlSdr(self.device_index)
            self._rtl.sample_rate = self.sample_rate
            logger.info("RTL-SDR initialized (device_index=%s)", self.device_index)
        except ImportError:
            logger.warning("pyrtlsdr not installed; RTL-SDR backend will yield stub samples")
        except Exception as e:
            logger.warning("RTL-SDR init failed: %s", e)

    async def set_frequency(self, frequency_hz: float) -> None:
        """Tune to frequency in Hz."""
        self._frequency_hz = frequency_hz
        if self._rtl:
            self._rtl.center_freq = int(frequency_hz)

    async def receive(self, duration_seconds: float) -> AsyncIterator[SignalSample]:
        """Stream signal samples: read I/Q in chunks, compute power (dB), yield SignalSample."""
        loop = asyncio.get_running_loop()
        end = loop.time() + duration_seconds
        chunk_size = 8192
        while loop.time() < end:
            if self._rtl:
                try:
                    samples = await loop.run_in_executor(
                        None,
                        lambda: self._rtl.read_samples(chunk_size),
                    )
                    power = np.mean(np.abs(samples) ** 2)
                    strength_db = 10.0 * np.log10(power + 1e-30) if power > 0 else -120.0
                except Exception as e:
                    logger.debug("RTL-SDR read failed: %s", e)
                    strength_db = -100.0
            else:
                strength_db = -100.0
            yield SignalSample(
                timestamp=datetime.now(timezone.utc),
                frequency_hz=self._frequency_hz,
                strength_db=float(strength_db),
                decoded_data=None,
            )
            await asyncio.sleep(0.1)

    async def close(self) -> None:
        """Release RTL-SDR."""
        if self._rtl:
            try:
                self._rtl.close()
            except Exception as e:
                logger.warning("RTL-SDR close: %s", e)
            self._rtl = None
