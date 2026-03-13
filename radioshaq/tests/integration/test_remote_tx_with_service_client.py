from __future__ import annotations

import base64
from typing import Any

import pytest
import httpx

from radioshaq.radio.sdr_tx import HackRFServiceClient
from radioshaq.remote_receiver import server


class _FakeBroker:
    def __init__(self) -> None:
        self.tone_calls: list[dict[str, Any]] = []
        self.iq_calls: list[dict[str, Any]] = []
        self._available = True

    @property
    def available(self) -> bool:
        return self._available

    def request_tx(self) -> None:
        return None

    def clear_tx(self) -> None:
        return None

    async def tx_tone(self, *, frequency_hz: float, duration_sec: float, sample_rate: int) -> None:
        self.tone_calls.append(
            {
                "frequency_hz": frequency_hz,
                "duration_sec": duration_sec,
                "sample_rate": sample_rate,
            }
        )

    async def tx_iq(
        self,
        *,
        frequency_hz: float,
        sample_rate: int,
        iq_bytes: bytes,
        occupied_bandwidth_hz: float | None = None,
    ) -> None:
        self.iq_calls.append(
            {
                "frequency_hz": frequency_hz,
                "sample_rate": sample_rate,
                "len": len(iq_bytes),
                "occupied_bandwidth_hz": occupied_bandwidth_hz,
            }
        )


class _DeviceManager:
    def __init__(self) -> None:
        self.restricted_region = "FCC"


@pytest.mark.asyncio
async def test_hackrf_service_client_hits_remote_tx_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    # Wire a fake broker and device manager into the receiver app.
    broker = _FakeBroker()
    server.app.state.hackrf_broker = broker
    server.app.state.hackrf_broker_device_manager = _DeviceManager()

    # Permit all frequencies/spectrum for this test by stubbing compliance helpers.
    monkeypatch.setattr(server, "is_restricted", lambda *_, **__: False)
    monkeypatch.setattr(server, "is_tx_allowed", lambda *_, **__: True)
    monkeypatch.setattr(server, "is_tx_spectrum_allowed", lambda *_, **__: True)
    monkeypatch.setattr(server, "log_tx", lambda *_, **__: None)

    # Skip real JWT verification for TX auth.
    async def _accept_any_token(token: str) -> Any:
        return object()

    receiver: server.ReceiverService = server.app.state.receiver
    receiver.jwt_auth.verify_token = _accept_any_token  # type: ignore[assignment]

    # Route HackRFServiceClient HTTP calls into the receiver ASGI app.
    RealAsyncClient = httpx.AsyncClient

    class _AppAsyncClient(RealAsyncClient):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs.setdefault("app", server.app)
            kwargs.setdefault("base_url", "http://testserver")
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("radioshaq.radio.sdr_tx.httpx.AsyncClient", _AppAsyncClient)

    client = HackRFServiceClient(
        base_url="http://testserver",
        auth_token="SERVICETOKEN",
        allow_bands_only=False,
    )

    # Tone TX
    await client.transmit_tone(frequency_hz=145_000_000.0, duration_sec=0.05, sample_rate=2_000_000)
    assert broker.tone_calls

    # IQ TX
    iq = b"\x00\x01" * 64
    await client.transmit_iq(
        frequency_hz=145_000_000.0,
        samples_iq=iq,
        sample_rate=1_000_000,
        occupied_bandwidth_hz=12_500.0,
    )
    assert broker.iq_calls

