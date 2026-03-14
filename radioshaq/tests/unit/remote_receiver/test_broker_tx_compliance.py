from __future__ import annotations

import base64
from typing import Any

import pytest
from fastapi.testclient import TestClient

from radioshaq.remote_receiver.server import app, ensure_test_state, HackRFBroker


class _DummyBackend:
    def __init__(self, *, restricted: bool) -> None:
        self._restricted = restricted

    def get_restricted_bands_hz(self) -> list[tuple[float, float]]:
        if self._restricted:
            return [(144_000_000.0, 146_000_000.0)]
        return []

    def get_band_plans(self) -> dict[str, Any]:  # pragma: no cover - not used in these tests
        return {}


def _patch_compliance(monkeypatch: pytest.MonkeyPatch, *, restricted: bool) -> None:
    # Monkeypatch compliance_plugin backend used by is_restricted / is_tx_allowed.
    from radioshaq import compliance_plugin

    def _get_backend(region: str) -> Any:  # type: ignore[override]
        return _DummyBackend(restricted=restricted)

    monkeypatch.setattr(compliance_plugin, "get_backend", _get_backend)


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer DEMO"}


def test_tx_tone_rejected_when_restricted(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_compliance(monkeypatch, restricted=True)
    client = TestClient(app)
    resp = client.post(
        "/tx/tone",
        headers=_auth_headers(),
        json={"frequency_hz": 145_000_000.0, "duration_sec": 0.1, "sample_rate": 2_000_000},
    )
    assert resp.status_code == 403


def test_tx_tone_allows_when_not_restricted(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_compliance(monkeypatch, restricted=False)
    ensure_test_state(app)
    # Use a broker that reports available=True so we pass the 503 gate, then no-op TX.
    broker = HackRFBroker(device_manager=object())
    async def _noop_tx_tone(*args: Any, **kwargs: Any) -> None:
        return None
    broker.tx_tone = _noop_tx_tone  # type: ignore[assignment]
    app.state.hackrf_broker = broker

    client = TestClient(app)
    resp = client.post(
        "/tx/tone",
        headers=_auth_headers(),
        json={"frequency_hz": 145_000_000.0, "duration_sec": 0.1, "sample_rate": 2_000_000},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True


def test_tx_iq_rejected_when_not_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_compliance(monkeypatch, restricted=True)
    client = TestClient(app)
    iq_bytes = b"\x00" * 128
    b64 = base64.b64encode(iq_bytes).decode("ascii")
    resp = client.post(
        "/tx/iq",
        headers=_auth_headers(),
        json={
            "frequency_hz": 145_000_000.0,
            "sample_rate": 1_000_000,
            "iq_b64": b64,
            "occupied_bandwidth_hz": 12_500.0,
        },
    )
    assert resp.status_code == 403


def test_tx_iq_allows_when_compliant(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_compliance(monkeypatch, restricted=False)
    ensure_test_state(app)
    # Use a broker that reports available=True so we pass the 503 gate, then no-op TX.
    broker = HackRFBroker(device_manager=object())
    async def _noop_tx_iq(*args: Any, **kwargs: Any) -> None:
        return None
    broker.tx_iq = _noop_tx_iq  # type: ignore[assignment]
    app.state.hackrf_broker = broker

    client = TestClient(app)
    iq_bytes = b"\x00" * 128
    b64 = base64.b64encode(iq_bytes).decode("ascii")
    resp = client.post(
        "/tx/iq",
        headers=_auth_headers(),
        json={
            "frequency_hz": 145_000_000.0,
            "sample_rate": 1_000_000,
            "iq_b64": b64,
            "occupied_bandwidth_hz": 12_500.0,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True


def test_tx_tone_returns_503_when_broker_not_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """Broker present but broker.available is False: return 503 without calling request_tx()."""
    _patch_compliance(monkeypatch, restricted=False)
    ensure_test_state(app)
    # Force broker with no hardware (other tests may have set an available broker).
    app.state.hackrf_broker = HackRFBroker(device_manager=None)
    assert not app.state.hackrf_broker.available

    client = TestClient(app)
    resp = client.post(
        "/tx/tone",
        headers=_auth_headers(),
        json={"frequency_hz": 145_000_000.0, "duration_sec": 0.1, "sample_rate": 2_000_000},
    )
    assert resp.status_code == 503
    assert "not available" in resp.json().get("detail", "").lower()


def test_tx_iq_returns_503_when_broker_not_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """Broker present but broker.available is False: return 503 without calling request_tx()."""
    _patch_compliance(monkeypatch, restricted=False)
    ensure_test_state(app)
    app.state.hackrf_broker = HackRFBroker(device_manager=None)
    assert not app.state.hackrf_broker.available

    client = TestClient(app)
    iq_bytes = b"\x00" * 128
    b64 = base64.b64encode(iq_bytes).decode("ascii")
    resp = client.post(
        "/tx/iq",
        headers=_auth_headers(),
        json={
            "frequency_hz": 145_000_000.0,
            "sample_rate": 1_000_000,
            "iq_b64": b64,
            "occupied_bandwidth_hz": 12_500.0,
        },
    )
    assert resp.status_code == 503
    assert "not available" in resp.json().get("detail", "").lower()


def test_tx_returns_503_when_receiver_not_initialized(monkeypatch: pytest.MonkeyPatch) -> None:
    """When app.state.receiver is missing, _require_broker_auth returns 503 (not 500)."""
    _patch_compliance(monkeypatch, restricted=False)
    ensure_test_state(app)
    original_receiver = app.state.receiver
    try:
        app.state.receiver = None  # Simulate no lifespan / receiver not initialized
        client = TestClient(app)
        resp = client.post(
            "/tx/tone",
            headers=_auth_headers(),
            json={"frequency_hz": 145_000_000.0, "duration_sec": 0.1, "sample_rate": 2_000_000},
        )
        assert resp.status_code == 503
        assert "receiver" in resp.json().get("detail", "").lower() or "not initialized" in resp.json().get("detail", "").lower()
    finally:
        app.state.receiver = original_receiver

