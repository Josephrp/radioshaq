"""SDR transmitter abstraction (HackRF) with compliance checks and audit log."""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

import numpy as np
from loguru import logger

from radioshaq.radio.bands import BAND_PLANS, BandPlan
from radioshaq.radio.compliance import is_restricted, is_tx_allowed, log_tx


class SDRTransmitter(Protocol):
    """Protocol for SDR TX: compliance-checked transmit_tone / transmit_iq."""

    async def transmit_tone(
        self,
        frequency_hz: float,
        duration_sec: float,
        sample_rate: int = 2_000_000,
    ) -> None:
        """Transmit a simple test tone. Compliance is checked by caller or implementation."""
        ...

    async def transmit_iq(
        self,
        frequency_hz: float,
        samples_iq: Any,
        sample_rate: int,
    ) -> None:
        """Transmit I/Q samples (e.g. numpy complex or int8 interleaved)."""
        ...


class HackRFTransmitter:
    """
    HackRF TX with compliance: is_tx_allowed / is_restricted before TX, log_tx after.
    Requires python_hackrf (pip install python-hackrf), libhackrf >= 2024.02.1.
    """

    def __init__(
        self,
        device_index: int = 0,
        serial_number: str | None = None,
        max_gain: int = 47,
        allow_bands_only: bool = True,
        audit_log_path: str | None = None,
        restricted_region: str = "FCC",
        band_plan_source: dict[str, BandPlan] | None = None,
    ):
        self.device_index = device_index
        self.serial_number = serial_number
        self.max_gain = min(47, max(0, max_gain))
        self.allow_bands_only = allow_bands_only
        self.audit_log_path = audit_log_path
        self.restricted_region = restricted_region
        self._band_plan_source = band_plan_source
        self._device = None

    def _check_compliance(self, frequency_hz: float) -> None:
        """Raise ValueError if TX not allowed on this frequency."""
        if is_restricted(frequency_hz, region=self.restricted_region):
            raise ValueError(f"Frequency {frequency_hz} Hz is in a restricted band (no TX allowed)")
        plans = self._band_plan_source if self._band_plan_source is not None else BAND_PLANS
        if self.allow_bands_only and not is_tx_allowed(
            frequency_hz,
            band_plan_source=plans,
            allow_tx_only_amateur_bands=True,
            restricted_region=self.restricted_region,
        ):
            raise ValueError(f"Frequency {frequency_hz} Hz is not in an allowed band")

    def _audit(self, frequency_hz: float, duration_sec: float, mode: str = "tone") -> None:
        """Write TX audit log."""
        log_tx(
            frequency_hz=frequency_hz,
            duration_sec=duration_sec,
            mode=mode,
            rig_or_sdr="hackrf",
            operator_id=None,
            audit_log_path=self.audit_log_path,
        )

    def _open(self) -> Any:
        """Open HackRF device (lazy)."""
        if self._device is not None:
            return self._device
        try:
            from hackrf import HackRF
            if self.serial_number:
                self._device = HackRF(serial_number=self.serial_number)
            else:
                self._device = HackRF(device_index=self.device_index)
            return self._device
        except ImportError as e:
            raise RuntimeError(
                "HackRF TX requires python_hackrf. Install with: uv sync --extra hackrf (or pip install python-hackrf)"
            ) from e

    async def transmit_tone(
        self,
        frequency_hz: float,
        duration_sec: float,
        sample_rate: int = 2_000_000,
    ) -> None:
        """Transmit a simple CW-style tone. Compliance checked; audit logged."""
        self._check_compliance(frequency_hz)
        dev = self._open()
        loop = asyncio.get_running_loop()
        # Generate int8 interleaved I/Q for a tone (e.g. 1 kHz at sample_rate)
        import numpy as np
        tone_hz = 1000.0
        num_samples = int(duration_sec * sample_rate)
        t = np.arange(num_samples, dtype=np.float64) / sample_rate
        i = (127 * 0.3 * np.cos(2 * np.pi * tone_hz * t)).astype(np.int8)
        q = (127 * 0.3 * np.sin(2 * np.pi * tone_hz * t)).astype(np.int8)
        iq = np.empty(2 * num_samples, dtype=np.int8)
        iq[0::2] = i
        iq[1::2] = q
        def _blocking_tx() -> None:
            try:
                dev.center_freq = int(frequency_hz)
                dev.sample_rate = sample_rate
                dev.txvga_gain = self.max_gain
            except AttributeError:
                pass
            # python_hackrf TX: library may expose start_tx(callback) with
            # callback(transfer) where transfer has .buffer (int8). Fill and return 0/1.
            try:
                buf = iq.tobytes()
                sent = [0]
                def tx_cb(transfer: Any) -> int:
                    try:
                        blen = getattr(transfer, "buffer_length", None) or len(transfer.buffer)
                        start = sent[0]
                        if start >= len(buf):
                            return 1
                        end = min(start + blen, len(buf))
                        data = buf[start:end]
                        transfer.buffer[:len(data)] = data
                        sent[0] = end
                        return 1 if end >= len(buf) else 0
                    except Exception:
                        return 1
                dev.start_tx(tx_cb)
                import time
                time.sleep(duration_sec + 0.5)
                dev.stop_tx()
            except (AttributeError, TypeError) as e:
                logger.warning("HackRF TX not available (%s); audit only", e)
        try:
            await loop.run_in_executor(None, _blocking_tx)
        finally:
            self._audit(frequency_hz, duration_sec, "tone")

    async def transmit_iq(
        self,
        frequency_hz: float,
        samples_iq: Any,
        sample_rate: int,
    ) -> None:
        """Transmit I/Q samples. Compliance checked; audit logged."""
        self._check_compliance(frequency_hz)
        # Convert to int8 interleaved if needed, then same as tone path
        s = np.asarray(samples_iq)
        if np.iscomplexobj(s):
            i = (np.clip(np.real(s) * 127, -128, 127)).astype(np.int8)
            q = (np.clip(np.imag(s) * 127, -128, 127)).astype(np.int8)
            iq = np.empty(2 * len(s), dtype=np.int8)
            iq[0::2] = i
            iq[1::2] = q
        else:
            iq = np.asarray(s, dtype=np.int8)
        duration_sec = len(iq) / (2.0 * sample_rate)
        dev = self._open()
        loop = asyncio.get_running_loop()
        def _blocking_tx() -> None:
            try:
                dev.center_freq = int(frequency_hz)
                dev.sample_rate = sample_rate
                dev.txvga_gain = self.max_gain
            except AttributeError:
                pass
            try:
                buf = iq.tobytes()
                sent = [0]
                def tx_cb(transfer: Any) -> int:
                    try:
                        blen = getattr(transfer, "buffer_length", None) or len(transfer.buffer)
                        start = sent[0]
                        if start >= len(buf):
                            return 1
                        end = min(start + blen, len(buf))
                        data = buf[start:end]
                        transfer.buffer[:len(data)] = data
                        sent[0] = end
                        return 1 if end >= len(buf) else 0
                    except Exception:
                        return 1
                dev.start_tx(tx_cb)
                import time
                time.sleep(duration_sec + 0.5)
                dev.stop_tx()
            except (AttributeError, TypeError) as e:
                logger.warning("HackRF TX not available (%s); audit only", e)
        try:
            await loop.run_in_executor(None, _blocking_tx)
        finally:
            self._audit(frequency_hz, duration_sec, "iq")
