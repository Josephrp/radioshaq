"""Integration-style tests for HackRF broker mode and /tx/status endpoint."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient

from radioshaq.remote_receiver import server


def test_tx_status_not_configured_when_sdr_type_not_hackrf(monkeypatch):
    """With SDR_TYPE!=hackrf, /tx/status reports not configured."""
    os.environ["SDR_TYPE"] = "rtlsdr"
    with TestClient(server.app) as client:
        resp = client.get("/tx/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert data["reason"] == "hackrf_tx_not_configured"
    os.environ.pop("SDR_TYPE", None)


def test_tx_status_available_with_fake_hackrf_device_manager(monkeypatch):
    """With SDR_TYPE=hackrf and a fake HackRFDeviceManager, /tx/status reports available."""

    class _FakeHackRFDeviceManager(server.HackRFDeviceManager):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            # Avoid touching real hardware; just set minimal attributes.
            self._device_index = 0
            self._serial_number = None
            self._max_gain = 20
            self._restricted_region = "FCC"
            self._device = object()
            import asyncio

            self._lock = asyncio.Lock()

    monkeypatch.setattr(server, "HackRFDeviceManager", _FakeHackRFDeviceManager)
    os.environ["SDR_TYPE"] = "hackrf"
    with TestClient(server.app) as client:
        resp = client.get("/tx/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is True
        assert data["reason"] == "ok"
    os.environ.pop("SDR_TYPE", None)

