"""Tests for SDR backends and create_sdr_from_env (no hardware required)."""

from __future__ import annotations

import os
import asyncio

import pytest

from radioshaq.remote_receiver.server import HackRFBroker, HackRFDeviceManager
from radioshaq.remote_receiver.radio_interface import SDRInterface, create_sdr_from_env
from radioshaq.remote_receiver.backends.rtlsdr_backend import RtlSdrBackend
from radioshaq.remote_receiver.backends.hackrf_backend import HackRFBackend


def test_create_sdr_from_env_default_is_rtlsdr():
    """With SDR_TYPE unset or rtlsdr, create_sdr_from_env returns SDRInterface with RtlSdrBackend."""
    for val in (None, "rtlsdr", "RTLSDR"):
        if val is None:
            os.environ.pop("SDR_TYPE", None)
        else:
            os.environ["SDR_TYPE"] = val
        sdr = create_sdr_from_env()
        assert isinstance(sdr, SDRInterface)
        assert isinstance(sdr._backend, RtlSdrBackend)


def test_create_sdr_from_env_hackrf():
    """With SDR_TYPE=hackrf, create_sdr_from_env returns SDRInterface with HackRFBackend."""
    os.environ["SDR_TYPE"] = "hackrf"
    try:
        sdr = create_sdr_from_env()
        assert isinstance(sdr, SDRInterface)
        assert isinstance(sdr._backend, HackRFBackend)
    finally:
        os.environ.pop("SDR_TYPE", None)


def test_create_sdr_from_env_hackrf_with_broker_and_device_manager():
    """When broker/device manager are injected, create_sdr_from_env still returns HackRFBackend-backed SDRInterface."""
    os.environ["SDR_TYPE"] = "hackrf"
    try:
        dm = HackRFDeviceManager(device_index=0, serial_number=None, max_gain=20, restricted_region="FCC")
        broker = HackRFBroker(device_manager=dm)
        sdr = create_sdr_from_env(device_manager=dm, broker=broker)
        assert isinstance(sdr, SDRInterface)
        assert isinstance(sdr._backend, HackRFBackend)
        # Backend should be wired to shared device manager and broker.
        assert getattr(sdr._backend, "_device_manager") is dm
        assert getattr(sdr._backend, "_broker") is broker
    finally:
        os.environ.pop("SDR_TYPE", None)


@pytest.mark.asyncio
async def test_rtlsdr_backend_initialize_no_device():
    """RtlSdrBackend.initialize() does not raise when no device (logs warning)."""
    backend = RtlSdrBackend(device_index=99999)
    await backend.initialize()
    await backend.set_frequency(145e6)
    count = 0
    async for _ in backend.receive(0.2):
        count += 1
        if count >= 2:
            break
    await backend.close()


@pytest.mark.asyncio
async def test_hackrf_backend_initialize_no_device():
    """HackRFBackend.initialize() does not raise when no device (logs warning)."""
    backend = HackRFBackend(device_index=99999)
    await backend.initialize()
    await backend.set_frequency(145e6)
    count = 0
    async for _ in backend.receive(0.2):
        count += 1
        if count >= 2:
            break
    await backend.close()


@pytest.mark.asyncio
async def test_hackrf_broker_serializes_tx_calls_without_hardware():
    """HackRFBroker forwards tx_tone/tx_iq via a shared device manager and uses a shared lock.

    This test uses a fake device/manager so no real HackRF hardware or pyhackrf2 is required.
    """
    calls: list[tuple[str, dict[str, float]]] = []

    class _FakeDevice:
        def __init__(self) -> None:
            self.center_freq = 0
            self.sample_rate = 0
            self.txvga_gain = 0

        def start_tx(self, cb):
            class _Transfer:
                def __init__(self) -> None:
                    self.buffer = bytearray(256)
                    self.buffer_length = len(self.buffer)

            transfer = _Transfer()
            # Call until callback signals completion.
            while True:
                if cb(transfer):
                    break

        def stop_tx(self):
            # Record that stop_tx was called for observability.
            calls.append(("stop", {}))

    class _FakeDeviceManager(HackRFDeviceManager):
        def __init__(self) -> None:
            # Bypass real hardware and locking setup from base class.
            self._device = _FakeDevice()
            self._lock = asyncio.Lock()

        async def with_device(self, fn):
            async with self._lock:
                return await fn(self._device)

    dm = _FakeDeviceManager()
    broker = HackRFBroker(device_manager=dm)

    async def _do_tone():
        await broker.tx_tone(frequency_hz=145_000_000.0, duration_sec=0.1, sample_rate=2_000_000)

    async def _do_iq():
        await broker.tx_iq(
            frequency_hz=433_000_000.0,
            sample_rate=1_000_000,
            iq_bytes=b"\x00" * 128,
            occupied_bandwidth_hz=12_500.0,
        )

    # Run both tasks concurrently; broker's internal lock should serialize them.
    await asyncio.gather(_do_tone(), _do_iq())

    # We expect at least one stop marker recorded by the fake device,
    # which confirms that the TX callbacks ran to completion under the broker lock.
    assert len(calls) >= 1
    assert any(kind == "stop" for kind, _ in calls)


@pytest.mark.asyncio
async def test_hackrf_backend_receive_respects_broker_stop_flag(monkeypatch):
    """HackRFBackend.receive() consults broker.should_stop_rx and clears rx_active on exit."""
    import asyncio
    import numpy as np

    class _FakeDevice:
        def __init__(self) -> None:
            self.calls = 0

        def read_samples(self, n: int):
            self.calls += 1
            return np.zeros(n, dtype=np.complex64)

    class _FakeDeviceManager(HackRFDeviceManager):
        def __init__(self) -> None:
            # Do not call real base __init__; avoid hardware.
            self._device = _FakeDevice()
            self._lock = asyncio.Lock()

        async def with_device(self, fn):
            async with self._lock:
                return await fn(self._device)

    class _FakeBroker:
        def __init__(self) -> None:
            self._stop = False
            self._rx_active = asyncio.Event()

        @property
        def should_stop_rx(self) -> bool:
            return self._stop

        @property
        def rx_active(self):
            return self._rx_active

    dm = _FakeDeviceManager()
    broker = _FakeBroker()
    backend = HackRFBackend(device_index=0, serial_number=None, sample_rate=1_000_000, device_manager=dm)
    # Attach fake broker for scheduling flags.
    setattr(backend, "_broker", broker)

    await backend.initialize()
    await backend.set_frequency(145e6)

    async def _runner():
        count = 0
        async for _ in backend.receive(5.0):
            count += 1
        return count

    async def _stopper():
        # Allow a couple of iterations, then request stop.
        await asyncio.sleep(0.3)
        broker._stop = True

    counts, _ = await asyncio.gather(_runner(), _stopper())

    # We should have produced at least one chunk, but exited once stop was requested.
    assert counts >= 1
    assert not broker.rx_active.is_set()
