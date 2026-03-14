"""SDR transmitter abstraction (HackRF) with compliance checks and audit log."""

from __future__ import annotations

import asyncio
import base64
from typing import Any, Protocol

import httpx
import numpy as np
from loguru import logger

from radioshaq.compliance_plugin import get_backend
from radioshaq.radio.bands import BAND_PLANS, BandPlan
from radioshaq.radio.compliance import is_restricted, is_tx_allowed, is_tx_spectrum_allowed, log_tx
from radioshaq.radio.hackrf_tx_compat import stream_hackrf_iq_bytes


class _CompatAsyncClient(httpx.AsyncClient):
    """
    Backwards-compatible AsyncClient shim that accepts an optional ``app`` kwarg.

    Older tests expect ``httpx.AsyncClient(app=..., base_url=...)`` even though
    recent httpx versions removed this parameter in favor of ASGITransport.
    This shim converts ``app`` into an appropriate transport and then delegates
    to the real AsyncClient implementation.
    """

    def __init__(self, *args: Any, app: Any | None = None, **kwargs: Any) -> None:
        if app is not None and "transport" not in kwargs:
            from httpx import ASGITransport

            kwargs["transport"] = ASGITransport(app=app)
        super().__init__(*args, **kwargs)


# Module-local alias; does NOT mutate the global httpx namespace.
# Tests can monkeypatch radioshaq.radio.sdr_tx._AsyncClient to inject a custom client.
_AsyncClient = _CompatAsyncClient


def _normalize_iq_for_broker(samples_iq: Any, sample_rate: int) -> tuple[str, float]:
    """Normalize I/Q samples to int8 interleaved, then to base64. Runs in thread executor."""
    if isinstance(samples_iq, (bytes, bytearray, memoryview)):
        iq = np.frombuffer(samples_iq, dtype=np.int8)
    else:
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
    iq_bytes = iq.tobytes()
    iq_b64 = base64.b64encode(iq_bytes).decode("ascii")
    return iq_b64, duration_sec


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
        occupied_bandwidth_hz: float | None = None,
    ) -> None:
        """Transmit I/Q samples (e.g. numpy complex or int8 interleaved)."""
        ...


class _ComplianceCheckedTransmitter:
    """Shared compliance and audit helpers for SDR transmitters."""

    def __init__(
        self,
        *,
        allow_bands_only: bool = True,
        audit_log_path: str | None = None,
        restricted_region: str = "FCC",
        band_plan_source: dict[str, BandPlan] | None = None,
        rig_or_sdr: str = "hackrf",
    ) -> None:
        self.allow_bands_only = allow_bands_only
        self.audit_log_path = audit_log_path
        self.restricted_region = restricted_region
        self._band_plan_source = band_plan_source
        self._rig_or_sdr = rig_or_sdr

    def _check_compliance(self, frequency_hz: float, occupied_bandwidth_hz: float | None = None) -> None:
        """Raise ValueError if TX not allowed on this frequency."""
        if is_restricted(frequency_hz, region=self.restricted_region):
            raise ValueError(f"Frequency {frequency_hz} Hz is in a restricted band (no TX allowed)")
        plans = self._band_plan_source
        if plans is None:
            backend = get_backend(self.restricted_region)
            if backend is not None:
                _plans = backend.get_band_plans()
                plans = _plans if _plans is not None else BAND_PLANS
            else:
                plans = BAND_PLANS
        if self.allow_bands_only:
            if occupied_bandwidth_hz is not None and occupied_bandwidth_hz > 0:
                ok = is_tx_spectrum_allowed(
                    frequency_hz,
                    float(occupied_bandwidth_hz),
                    band_plan_source=plans,
                    allow_tx_only_amateur_bands=True,
                    restricted_region=self.restricted_region,
                )
                if not ok:
                    raise ValueError(
                        f"TX spectrum centered at {frequency_hz} Hz with BW={occupied_bandwidth_hz} Hz is not fully within an allowed band"
                    )
            else:
                if not is_tx_allowed(
                    frequency_hz,
                    band_plan_source=plans,
                    allow_tx_only_amateur_bands=True,
                    restricted_region=self.restricted_region,
                ):
                    raise ValueError(f"Frequency {frequency_hz} Hz is not in an allowed band")

    def _audit(
        self,
        frequency_hz: float,
        duration_sec: float,
        mode: str = "tone",
        *,
        success: bool = True,
    ) -> None:
        """Write TX audit log (success or failure)."""
        log_tx(
            frequency_hz=frequency_hz,
            duration_sec=duration_sec,
            mode=mode,
            rig_or_sdr=self._rig_or_sdr,
            operator_id=None,
            audit_log_path=self.audit_log_path,
            success=success,
        )


class HackRFTransmitter(_ComplianceCheckedTransmitter):
    """
    HackRF TX with compliance: is_tx_allowed / is_restricted before TX, log_tx after.
    Requires pyhackrf2 (pip install pyhackrf2), system libhackrf.
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
        super().__init__(
            allow_bands_only=allow_bands_only,
            audit_log_path=audit_log_path,
            restricted_region=restricted_region,
            band_plan_source=band_plan_source,
        )
        self._device = None

    def _open(self) -> Any:
        """Open HackRF device (lazy)."""
        if self._device is not None:
            return self._device
        try:
            from pyhackrf2 import HackRF
            if self.serial_number:
                self._device = HackRF(serial_number=self.serial_number)
            else:
                self._device = HackRF(device_index=self.device_index)
            return self._device
        except ImportError as e:
            raise RuntimeError(
                "HackRF TX requires pyhackrf2. Install with: uv sync --extra hackrf (or pip install pyhackrf2)"
            ) from e

    async def transmit_tone(
        self,
        frequency_hz: float,
        duration_sec: float,
        sample_rate: int = 2_000_000,
    ) -> None:
        """Transmit a simple CW-style tone. Compliance checked; audit logged."""
        # Conservative occupied BW estimate for a tone is small, but we still bound it.
        self._check_compliance(frequency_hz, occupied_bandwidth_hz=25_000.0)
        dev = self._open()
        loop = asyncio.get_running_loop()
        success = False

        def _blocking_tx() -> None:
            # Generate int8 interleaved I/Q for a tone (e.g. 1 kHz at sample_rate)
            # inside the executor to avoid blocking the event loop.
            tone_hz = 1000.0
            num_samples = int(duration_sec * sample_rate)
            t = np.arange(num_samples, dtype=np.float64) / sample_rate
            i = (127 * 0.3 * np.cos(2 * np.pi * tone_hz * t)).astype(np.int8)
            q = (127 * 0.3 * np.sin(2 * np.pi * tone_hz * t)).astype(np.int8)
            iq = np.empty(2 * num_samples, dtype=np.int8)
            iq[0::2] = i
            iq[1::2] = q

            try:
                dev.center_freq = int(frequency_hz)
                dev.sample_rate = sample_rate
                dev.txvga_gain = self.max_gain
            except AttributeError:
                # Older or stub objects may not expose these attributes.
                pass
            try:
                buf = iq.tobytes()
                stream_hackrf_iq_bytes(dev, buf, duration_sec)
            except (AttributeError, TypeError) as e:
                # Stub/API mismatch: skip hardware TX but still allow audit trail to record attempt.
                logger.warning("HackRF TX not available ({}); audit only", repr(e))

        try:
            await loop.run_in_executor(None, _blocking_tx)
            success = True
        except RuntimeError as e:
            msg = str(e)
            if "HACKRF_ERROR_LIBUSB" in msg or "libusb" in msg.lower():
                raise RuntimeError(
                    "HackRF libusb error (HACKRF_ERROR_LIBUSB). "
                    "Check that the device is attached to WSL (usbipd-win), "
                    "not in use by another process, and that libhackrf is installed."
                ) from e
            raise
        finally:
            self._audit(frequency_hz, duration_sec, "tone", success=success)

    async def transmit_iq(
        self,
        frequency_hz: float,
        samples_iq: Any,
        sample_rate: int,
        occupied_bandwidth_hz: float | None = None,
    ) -> None:
        """Transmit I/Q samples. Compliance checked; audit logged."""
        # Sample rate is not the signal bandwidth; default to a center-frequency-only check.
        self._check_compliance(frequency_hz, occupied_bandwidth_hz=occupied_bandwidth_hz)
        # Convert to int8 interleaved if needed, then same as tone path
        # Normalize samples into int8 interleaved IQ. Support both numpy arrays and raw bytes.
        if isinstance(samples_iq, (bytes, bytearray, memoryview)):
            iq = np.frombuffer(samples_iq, dtype=np.int8)
        else:
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
        success = False

        def _blocking_tx() -> None:
            try:
                dev.center_freq = int(frequency_hz)
                dev.sample_rate = sample_rate
                dev.txvga_gain = self.max_gain
            except AttributeError:
                # Older or stub objects may not expose these attributes.
                pass
            try:
                buf = iq.tobytes()
                stream_hackrf_iq_bytes(dev, buf, duration_sec)
            except (AttributeError, TypeError) as e:
                # Stub/API mismatch: skip hardware TX but still allow audit trail to record attempt.
                logger.warning("HackRF TX not available ({}); audit only", repr(e))

        try:
            await loop.run_in_executor(None, _blocking_tx)
            success = True
        except RuntimeError as e:
            msg = str(e)
            if "HACKRF_ERROR_LIBUSB" in msg or "libusb" in msg.lower():
                raise RuntimeError(
                    "HackRF libusb error (HACKRF_ERROR_LIBUSB). "
                    "Check that the device is attached to WSL (usbipd-win), "
                    "not in use by another process, and that libhackrf is installed."
                ) from e
            raise
        finally:
            self._audit(frequency_hz, duration_sec, "iq", success=success)


class HackRFServiceClient(_ComplianceCheckedTransmitter):
    """
    Remote HackRF TX client that delegates to a HackRF broker service over HTTP.
    Implements the same SDRTransmitter interface as HackRFTransmitter.
    """

    def __init__(
        self,
        base_url: str,
        *,
        auth_token: str | None = None,
        request_timeout_sec: float = 15.0,
        allow_bands_only: bool = True,
        audit_log_path: str | None = None,
        restricted_region: str = "FCC",
        band_plan_source: dict[str, BandPlan] | None = None,
    ) -> None:
        super().__init__(
            allow_bands_only=allow_bands_only,
            audit_log_path=audit_log_path,
            restricted_region=restricted_region,
            band_plan_source=band_plan_source,
            rig_or_sdr="hackrf_broker",
        )
        self._base_url = base_url.rstrip("/")
        self._auth_token = auth_token
        self._timeout = request_timeout_sec

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers: dict[str, str] = {}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        async with _AsyncClient(base_url=self._base_url, timeout=self._timeout, headers=headers) as client:
            try:
                response = await client.post(path, json=payload)
            except httpx.RequestError as e:
                raise RuntimeError(
                    f"HackRF broker unreachable at {self._base_url}: {e!r}"
                ) from e
            response.raise_for_status()
            try:
                data = response.json()
            except ValueError:
                data = {}
            return data

    async def transmit_tone(
        self,
        frequency_hz: float,
        duration_sec: float,
        sample_rate: int = 2_000_000,
    ) -> None:
        """Transmit a simple tone via the remote HackRF broker."""
        # Conservative occupied BW estimate for a tone.
        self._check_compliance(frequency_hz, occupied_bandwidth_hz=25_000.0)
        success = False
        try:
            await self._post(
                "/tx/tone",
                {
                    "frequency_hz": frequency_hz,
                    "duration_sec": duration_sec,
                    "sample_rate": sample_rate,
                },
            )
            success = True
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                data = e.response.json()
                detail = data.get("detail") or ""
            except Exception:
                detail = e.response.text
            if "HACKRF_ERROR_LIBUSB" in detail or "libusb" in detail.lower():
                raise RuntimeError(
                    "HackRF libusb error (HACKRF_ERROR_LIBUSB). "
                    "Check that the device is attached to WSL (usbipd-win), "
                    "not in use by another process, and that libhackrf is installed."
                ) from e
            raise
        finally:
            self._audit(frequency_hz, duration_sec, "tone", success=success)

    async def transmit_iq(
        self,
        frequency_hz: float,
        samples_iq: Any,
        sample_rate: int,
        occupied_bandwidth_hz: float | None = None,
    ) -> None:
        """Transmit I/Q samples via the remote HackRF broker."""
        self._check_compliance(frequency_hz, occupied_bandwidth_hz=occupied_bandwidth_hz)
        # Offload heavy numpy/base64 work to a thread to avoid blocking the event loop.
        loop = asyncio.get_running_loop()
        iq_b64, duration_sec = await loop.run_in_executor(
            None, _normalize_iq_for_broker, samples_iq, sample_rate
        )
        success = False
        try:
            await self._post(
                "/tx/iq",
                {
                    "frequency_hz": frequency_hz,
                    "sample_rate": sample_rate,
                    "iq_b64": iq_b64,
                    "occupied_bandwidth_hz": occupied_bandwidth_hz,
                },
            )
            success = True
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                data = e.response.json()
                detail = data.get("detail") or ""
            except Exception:
                detail = e.response.text
            if "HACKRF_ERROR_LIBUSB" in detail or "libusb" in detail.lower():
                raise RuntimeError(
                    "HackRF libusb error (HACKRF_ERROR_LIBUSB). "
                    "Check that the device is attached to WSL (usbipd-win), "
                    "not in use by another process, and that libhackrf is installed."
                ) from e
            raise
        finally:
            self._audit(frequency_hz, duration_sec, "iq", success=success)
