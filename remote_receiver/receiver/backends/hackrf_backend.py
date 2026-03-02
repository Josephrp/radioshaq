"""HackRF RX backend (python_hackrf)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import AsyncIterator

import numpy as np
from loguru import logger

from receiver.backends.base import SDRBackend
from receiver.radio_interface import SignalSample


class HackRFBackend(SDRBackend):
    """HackRF receive backend using python_hackrf. Pip: python-hackrf (libhackrf 2024.02.1+)."""

    def __init__(
        self,
        device_index: int = 0,
        serial_number: str | None = None,
        sample_rate: int = 10_000_000,
    ):
        self.device_index = device_index
        self.serial_number = serial_number
        self.sample_rate = sample_rate
        self._frequency_hz: float = 0.0
        self._device = None

    async def initialize(self) -> None:
        """Open HackRF device by index or serial."""
        try:
            from hackrf import HackRF
            if self.serial_number:
                self._device = HackRF(serial_number=self.serial_number)
            else:
                self._device = HackRF(device_index=self.device_index)
            self._device.sample_rate = self.sample_rate
            logger.info(
                "HackRF initialized (index=%s, serial=%s)",
                self.device_index,
                self.serial_number or "default",
            )
        except ImportError:
            logger.warning(
                "python_hackrf not installed; install with: uv sync --extra hackrf"
            )
        except Exception as e:
            logger.warning("HackRF init failed: %s", e)

    async def set_frequency(self, frequency_hz: float) -> None:
        """Tune to frequency in Hz (1 MHz–6 GHz)."""
        self._frequency_hz = frequency_hz
        if self._device:
            self._device.center_freq = int(frequency_hz)

    async def receive(self, duration_seconds: float) -> AsyncIterator[SignalSample]:
        """Stream signal samples: read I/Q via read_samples, compute power -> dB."""
        loop = asyncio.get_running_loop()
        end = loop.time() + duration_seconds
        num_samples = 8192
        while loop.time() < end:
            if self._device:
                try:
                    # python_hackrf: read_samples returns numpy array (complex or I/Q)
                    samples = await loop.run_in_executor(
                        None,
                        lambda: self._device.read_samples(num_samples),
                    )
                    if hasattr(samples, "dtype") and np.iscomplexobj(samples):
                        power = np.mean(np.abs(samples) ** 2)
                    else:
                        power = np.mean(np.abs(samples) ** 2)
                    strength_db = 10.0 * np.log10(power + 1e-30) if power > 0 else -120.0
                except Exception as e:
                    logger.debug("HackRF read failed: %s", e)
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
        """Release HackRF."""
        if self._device:
            try:
                self._device.close()
            except Exception as e:
                logger.warning("HackRF close: %s", e)
            self._device = None
