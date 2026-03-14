"""RTL-SDR backend with real I/Q streaming."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
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


class RtlSdrBackend(SDRBackend):
    """RTL-SDR backend: real I/Q via pyrtlsdr read_samples, power -> dB."""

    def __init__(self, device_index: int = 0, sample_rate: int = 2_400_000):
        self.device_index = device_index
        self.sample_rate = sample_rate
        self._frequency_hz: float = 0.0
        self._rtl = None
        self._rx_mode = os.environ.get("RECEIVER_MODE", "none").strip().lower()
        self._audio_rate = int(os.environ.get("RECEIVER_AUDIO_RATE", "48000"))
        self._bfo_hz = float(os.environ.get("RECEIVER_BFO_HZ", "1500"))
        self._nfm: NfmDemodulator | None = None
        self._am: AmDemodulator | None = None
        self._ssb: SsbDemodulator | None = None
        self._cw: CwAudioDemodulator | None = None

    async def initialize(self) -> None:
        """Open RTL-SDR device."""
        try:
            import rtlsdr

            self._rtl = rtlsdr.RtlSdr(self.device_index)
            self._rtl.sample_rate = self.sample_rate
            logger.info("RTL-SDR initialized (device_index={})", self.device_index)
        except ImportError:
            logger.warning("pyrtlsdr not installed; RTL-SDR backend will yield stub samples")
        except Exception as e:
            logger.warning("RTL-SDR init failed: {}", e)

    async def set_frequency(self, frequency_hz: float) -> None:
        """Tune to frequency in Hz."""
        self._frequency_hz = frequency_hz
        if self._rtl:
            self._rtl.center_freq = int(frequency_hz)
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
        self._nfm = None
        self._am = None
        self._ssb = None
        self._cw = None

    async def receive(self, duration_seconds: float) -> AsyncIterator[SignalSample]:
        """Stream signal samples: read I/Q in chunks, compute power (dB), yield SignalSample."""
        loop = asyncio.get_running_loop()
        end = loop.time() + duration_seconds
        chunk_size = 8192
        while loop.time() < end:
            audio_pcm: bytes | None = None
            if self._rtl:
                try:
                    samples = await loop.run_in_executor(
                        None,
                        lambda: self._rtl.read_samples(chunk_size),
                    )
                    s = np.asarray(samples)
                    power = np.mean(np.abs(s) ** 2)
                    strength_db = 10.0 * np.log10(power + 1e-30) if power > 0 else -120.0
                    # Run CPU-heavy demod in executor to avoid blocking the event loop (same as hackrf_backend).
                    if self._rx_mode in {"nfm", "fm"}:
                        if self._nfm is None:
                            self._nfm = NfmDemodulator(
                                NfmConfig(audio_rate_hz=self._audio_rate),
                                rf_rate_hz=self.sample_rate,
                            )
                        nfm = self._nfm
                        audio_pcm = await loop.run_in_executor(
                            None, lambda: float_to_pcm16(nfm.demod(s))
                        )
                    elif self._rx_mode in {"am"}:
                        if self._am is None:
                            self._am = AmDemodulator(
                                AnalogConfig(audio_rate_hz=self._audio_rate, bfo_hz=self._bfo_hz),
                                rf_rate_hz=self.sample_rate,
                            )
                        am = self._am
                        audio_pcm = await loop.run_in_executor(
                            None, lambda: float_to_pcm16(am.demod(s))
                        )
                    elif self._rx_mode in {"usb", "lsb"}:
                        if self._ssb is None:
                            self._ssb = SsbDemodulator(
                                AnalogConfig(audio_rate_hz=self._audio_rate, bfo_hz=self._bfo_hz),
                                rf_rate_hz=self.sample_rate,
                                sideband=self._rx_mode.upper(),
                            )
                        ssb = self._ssb
                        audio_pcm = await loop.run_in_executor(
                            None, lambda: float_to_pcm16(ssb.demod(s))
                        )
                    elif self._rx_mode in {"cw"}:
                        if self._cw is None:
                            self._cw = CwAudioDemodulator(
                                AnalogConfig(audio_rate_hz=self._audio_rate, bfo_hz=self._bfo_hz),
                                rf_rate_hz=self.sample_rate,
                            )
                        cw = self._cw
                        audio_pcm = await loop.run_in_executor(
                            None, lambda: float_to_pcm16(cw.demod(s))
                        )
                except Exception as e:
                    logger.debug("RTL-SDR read failed: {}", e)
                    strength_db = -100.0
            else:
                strength_db = -100.0
            yield SignalSample(
                timestamp=datetime.now(timezone.utc),
                frequency_hz=self._frequency_hz,
                strength_db=float(strength_db),
                decoded_data=None,
                raw_data=audio_pcm,
                mode=self._rx_mode if self._rx_mode != "none" else "",
            )
            await asyncio.sleep(0.1)

    async def close(self) -> None:
        """Release RTL-SDR."""
        if self._rtl:
            try:
                self._rtl.close()
            except Exception as e:
                logger.warning("RTL-SDR close: {}", e)
            self._rtl = None
