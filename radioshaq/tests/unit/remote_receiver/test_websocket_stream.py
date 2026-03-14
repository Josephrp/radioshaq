from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi.testclient import TestClient

from radioshaq.remote_receiver.auth import ReceiverTokenPayload
from radioshaq.remote_receiver.radio_interface import SDRInterface, SignalSample
from radioshaq.remote_receiver.server import app, ReceiverService


class _FakeRadio(SDRInterface):
    def __init__(self, samples: list[SignalSample]) -> None:
        # Bypass SDRInterface.__init__; we don't need a real backend.
        self._samples = samples

    async def initialize(self) -> None:  # type: ignore[override]
        return None

    async def set_frequency(self, frequency_hz: float) -> None:  # type: ignore[override]
        self._frequency = frequency_hz

    async def configure(  # type: ignore[override]
        self,
        *,
        mode: str | None = None,
        audio_rate_hz: int | None = None,
        bfo_hz: float | None = None,
    ) -> None:
        self._mode = mode
        self._audio_rate_hz = audio_rate_hz
        self._bfo_hz = bfo_hz

    async def receive(self, duration_seconds: float) -> AsyncIterator[SignalSample]:  # type: ignore[override]
        for s in self._samples:
            yield s

    async def close(self) -> None:  # type: ignore[override]
        """No-op for fake; avoids _backend.close() on lifespan shutdown."""
        return None


def _make_sample(with_audio: bool) -> SignalSample:
    raw = b"\x01\x02\x03\x04" if with_audio else None
    return SignalSample(
        timestamp=datetime.now(timezone.utc),
        frequency_hz=145_000_000.0,
        strength_db=-50.0,
        decoded_data="TEST",
        raw_data=raw,
        mode="nfm",
    )


def _setup_receiver_with_fake_radio(client: TestClient, samples: list[SignalSample]) -> str:
    receiver: ReceiverService = client.app.state.receiver
    receiver.radio = _FakeRadio(samples)

    async def _ok_verify(token: str) -> ReceiverTokenPayload:  # type: ignore[override]
        return ReceiverTokenPayload(sub="demo-op", role="field", station_id="STATION", scopes=[])

    receiver.jwt_auth.verify_token = _ok_verify  # type: ignore[assignment]
    return "DEMO_TOKEN"


def test_websocket_stream_happy_path():
    with TestClient(app) as client:
        token = _setup_receiver_with_fake_radio(
            client,
            [
                _make_sample(with_audio=False),
                _make_sample(with_audio=True),
            ],
        )
        with client.websocket_connect(
            f"/ws/stream?token={token}&frequency_hz=145000000&duration_seconds=2"
        ) as ws:
            seen_signal = False
            seen_audio = False
            for _ in range(4):
                msg = ws.receive_json()
                if msg.get("type") == "signal":
                    seen_signal = True
                    assert "timestamp" in msg
                    assert "frequency_hz" in msg
                    assert "signal_strength_db" in msg
                    assert "decoded_text" in msg
                    assert "mode" in msg
                elif msg.get("type") == "audio":
                    seen_audio = True
                    assert "sample_rate_hz" in msg
                    b64 = msg.get("audio_b64")
                    assert isinstance(b64, str)
                    decoded = base64.b64decode(b64.encode("ascii"))
                    assert decoded
            assert seen_signal
            assert seen_audio


def test_websocket_stream_invalid_token_yields_error_and_close(monkeypatch):
    with TestClient(app) as client:
        receiver: ReceiverService = client.app.state.receiver

        async def _bad_verify(token: str) -> Any:
            raise PermissionError("bad token")

        receiver.jwt_auth.verify_token = _bad_verify  # type: ignore[assignment]

        with client.websocket_connect(
            "/ws/stream?token=BAD&frequency_hz=145000000&duration_seconds=2"
        ) as ws:
            msg = ws.receive_json()
            assert msg.get("type") == "error"
            assert "Unauthorized" in msg.get("message", "")

