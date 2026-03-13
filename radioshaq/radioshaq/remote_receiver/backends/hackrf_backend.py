"""HackRF RX backend (pyhackrf2)."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import AsyncIterator

import numpy as np
from loguru import logger

from radioshaq.remote_receiver.backends.base import SDRBackend
from radioshaq.remote_receiver.radio_interface import SignalSample
from radioshaq.remote_receiver.dsp.nfm import NfmConfig, NfmDemodulator, float_to_pcm16
from radioshaq.remote_receiver.dsp.analog import (
    AnalogConfig,
    AmDemodulator,
    CwAudioDemodulator,
    SsbDemodulator,
)


class HackRFBackend(SDRBackend):
    """HackRF receive backend using pyhackrf2. Pip: pyhackrf2 (requires system libhackrf)."""

    def __init__(
        self,
        device_index: int = 0,
        serial_number: str | None = None,
        sample_rate: int = 10_000_000,
        device_manager: object | None = None,
        broker: object | None = None,
    ):
        self.device_index = device_index
        self.serial_number = serial_number
        self.sample_rate = sample_rate
        # When provided, device manager owns the single HackRF instance and
        # coordinates access across RX and TX. When absent, this backend
        # manages its own device (legacy mode).
        self._device_manager = device_manager
        # Optional broker for RX/TX scheduling flags (e.g. should_stop_rx, rx_active).
        self._broker = broker
        self._frequency_hz: float = 0.0
        self._device = None
        self._rx_mode = os.environ.get("RECEIVER_MODE", "none").strip().lower()
        self._audio_rate = int(os.environ.get("RECEIVER_AUDIO_RATE", "48000"))
        self._bfo_hz = float(os.environ.get("RECEIVER_BFO_HZ", "1500"))
        self._nfm: NfmDemodulator | None = None
        self._am: AmDemodulator | None = None
        self._ssb: SsbDemodulator | None = None
        self._cw: CwAudioDemodulator | None = None

    async def initialize(self) -> None:
        """Open HackRF device by index or serial (legacy mode only).

        When a shared device manager is provided, it is responsible for
        opening the underlying device so this method becomes a no-op.
        """
        if self._device_manager is not None:
            logger.info(
                "HackRFBackend using shared HackRFDeviceManager (index={}, serial={})",
                self.device_index,
                self.serial_number or "default",
            )
            return
        try:
            from pyhackrf2 import HackRF

            if self.serial_number:
                self._device = HackRF(serial_number=self.serial_number)
            else:
                self._device = HackRF(device_index=self.device_index)
            self._device.sample_rate = self.sample_rate
            logger.info(
                "HackRF initialized (index={}, serial={})",
                self.device_index,
                self.serial_number or "default",
            )
        except ImportError:
            logger.warning(
                "pyhackrf2 not installed; install with: uv sync --extra hackrf"
            )
        except Exception as e:
            logger.warning("HackRF init failed: {}", repr(e))

    async def set_frequency(self, frequency_hz: float) -> None:
        """Tune to frequency in Hz (1 MHz–6 GHz)."""
        self._frequency_hz = frequency_hz
        if self._device_manager is not None:
            loop = asyncio.get_running_loop()

            async def _set(dev) -> None:
                await loop.run_in_executor(
                    None, lambda: setattr(dev, "center_freq", int(frequency_hz))
                )

            try:
                await self._device_manager.with_device(_set)
            except Exception as e:
                logger.warning("HackRF set_frequency via manager failed: {}", repr(e))
        elif self._device:
            self._device.center_freq = int(frequency_hz)
        # Reset demod state on retune.
        self._nfm = None
        self._am = None
        self._ssb = None
        self._cw = None

    async def configure(
        self,
        *,
        mode: str | None = None,
        audio_rate_hz: int | None = None,
        bfo_hz: float | None = None,
    ) -> None:
        if mode is not None:
            self._rx_mode = str(mode).strip().lower()
        if audio_rate_hz is not None:
            self._audio_rate = int(audio_rate_hz)
        if bfo_hz is not None:
            self._bfo_hz = float(bfo_hz)
        # Reset state so settings take effect cleanly
        self._nfm = None
        self._am = None
        self._ssb = None
        self._cw = None

    async def receive(self, duration_seconds: float) -> AsyncIterator[SignalSample]:
        """Stream signal samples: read I/Q via read_samples, compute power -> dB."""
        loop = asyncio.get_running_loop()
        end = loop.time() + duration_seconds
        num_samples = 8192
        broker = getattr(self, "_broker", None)
        if broker is not None:
            broker.rx_active.set()
        try:
            while loop.time() < end:
                if broker is not None and broker.should_stop_rx:
                    break
                audio_pcm: bytes | None = None
                s = None
                strength_db = -120.0
                if self._device_manager is not None:

                    async def _read(dev):
                        return await loop.run_in_executor(
                            None, lambda: dev.read_samples(num_samples)
                        )

                    try:
                        samples = await self._device_manager.with_device(_read)
                        s = np.asarray(samples)
                        power = np.mean(np.abs(s) ** 2)
                        strength_db = (
                            10.0 * np.log10(power + 1e-30) if power > 0 else -120.0
                        )
                    except Exception as e:
                        logger.warning(
                            "HackRF read_samples() via manager failed: {}", repr(e)
                        )
                        strength_db = -100.0
                        s = None
                elif self._device:
                    try:
                        samples = await loop.run_in_executor(
                            None,
                            lambda: self._device.read_samples(num_samples),
                        )
                        # pyhackrf2 returns complex64 IQ.
                        s = np.asarray(samples)
                        power = np.mean(np.abs(s) ** 2)
                        strength_db = (
                            10.0 * np.log10(power + 1e-30) if power > 0 else -120.0
                        )
                    except Exception as e:
                        logger.warning("HackRF read_samples() failed: {}", repr(e))
                        strength_db = -100.0
                        s = None
                else:
                    strength_db = -100.0
                if s is not None:
                    try:
                        if self._rx_mode in {"nfm", "fm"}:
                            if self._nfm is None:
                                self._nfm = NfmDemodulator(
                                    NfmConfig(audio_rate_hz=self._audio_rate),
                                    rf_rate_hz=self.sample_rate,
                                )
                            audio = self._nfm.demod(s)
                            audio_pcm = float_to_pcm16(audio)
                        elif self._rx_mode in {"am"}:
                            if self._am is None:
                                self._am = AmDemodulator(
                                    AnalogConfig(
                                        audio_rate_hz=self._audio_rate,
                                        bfo_hz=self._bfo_hz,
                                    ),
                                    rf_rate_hz=self.sample_rate,
                                )
                            audio_pcm = float_to_pcm16(self._am.demod(s))
                        elif self._rx_mode in {"usb", "lsb"}:
                            if self._ssb is None:
                                self._ssb = SsbDemodulator(
                                    AnalogConfig(
                                        audio_rate_hz=self._audio_rate,
                                        bfo_hz=self._bfo_hz,
                                    ),
                                    rf_rate_hz=self.sample_rate,
                                    sideband=self._rx_mode.upper(),
                                )
                            audio_pcm = float_to_pcm16(self._ssb.demod(s))
                        elif self._rx_mode in {"cw"}:
                            if self._cw is None:
                                self._cw = CwAudioDemodulator(
                                    AnalogConfig(
                                        audio_rate_hz=self._audio_rate,
                                        bfo_hz=self._bfo_hz,
                                    ),
                                    rf_rate_hz=self.sample_rate,
                                )
                            audio_pcm = float_to_pcm16(self._cw.demod(s))
                    except Exception as e:
                        logger.warning(
                            "HackRF demodulation failed (mode={}): {}",
                            self._rx_mode,
                            repr(e),
                        )
                        audio_pcm = None
                yield SignalSample(
                    timestamp=datetime.now(timezone.utc),
                    frequency_hz=self._frequency_hz,
                    strength_db=float(strength_db),
                    decoded_data=None,
                    raw_data=audio_pcm,
                    mode=self._rx_mode if self._rx_mode != "none" else "",
                )
                await asyncio.sleep(0.1)
        finally:
            if broker is not None:
                broker.rx_active.clear()

    async def close(self) -> None:
        """Release HackRF."""
        if self._device:
            try:
                self._device.close()
            except Exception as e:
                logger.warning("HackRF close: {}", e)
            self._device = None
