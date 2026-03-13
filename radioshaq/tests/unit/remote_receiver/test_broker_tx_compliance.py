from __future__ import annotations

import base64
from typing import Any

import pytest
from fastapi.testclient import TestClient

from radioshaq.remote_receiver.server import app


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
    client = TestClient(app)

    # Prevent actual broker calls; just confirm compliance gate lets us through.
    broker = app.state.hackrf_broker

    async def _noop_tx_tone(*args: Any, **kwargs: Any) -> None:
        return None

    broker.tx_tone = _noop_tx_tone  # type: ignore[assignment]

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
    client = TestClient(app)
    iq_bytes = b"\x00" * 128
    b64 = base64.b64encode(iq_bytes).decode("ascii")

    broker = app.state.hackrf_broker

    async def _noop_tx_iq(*args: Any, **kwargs: Any) -> None:
        return None

    broker.tx_iq = _noop_tx_iq  # type: ignore[assignment]

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

