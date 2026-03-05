"""Tests for SDR backends and create_sdr_from_env (no hardware required)."""

from __future__ import annotations

import os

import pytest

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
