from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi.testclient import TestClient

from radioshaq.remote_receiver import server
from radioshaq.remote_receiver.radio_interface import SDRInterface, SignalSample


class _FakeRadio(SDRInterface):
    def __init__(self, samples: list[SignalSample]) -> None:
        self._samples = samples

    async def initialize(self) -> None:  # type: ignore[override]
        return None

    async def set_frequency(self, frequency_hz: float) -> None:  # type: ignore[override]
        self.frequency_hz = frequency_hz

    async def configure(  # type: ignore[override]
        self,
        *,
        mode: str | None = None,
        audio_rate_hz: int | None = None,
        bfo_hz: float | None = None,
    ) -> None:
        self.mode = mode
        self.audio_rate_hz = audio_rate_hz
        self.bfo_hz = bfo_hz

    async def receive(self, duration_seconds: float):  # type: ignore[override]
        # Simple async generator over the provided samples.
        for s in self._samples:
            yield s


def _setup_receiver_for_integration() -> str:
    receiver: server.ReceiverService = server.app.state.receiver
    # Replace real SDR backend with a deterministic fake.
    samples = [
        SignalSample(
            timestamp=datetime.now(timezone.utc),
            frequency_hz=145_000_000.0,
            strength_db=-40.0,
            decoded_data="HELLO",
            raw_data=b"\x00\x01",
            mode="nfm",
        )
    ]
    receiver.radio = _FakeRadio(samples)

    async def _ok_verify(token: str) -> Any:  # type: ignore[override]
        return server.JWTReceiverAuth(secret="stub").verify_token  # pragma: no cover

    # For this integration, simply skip real JWT verification and treat any token as valid.
    async def _accept_any_token(token: str) -> Any:
        class _Claims:
            sub = "integration-op"

        return _Claims()

    receiver.jwt_auth.verify_token = _accept_any_token  # type: ignore[assignment]
    # Use a dedicated upload queue we can inspect.
    receiver._upload_queue = asyncio.Queue()
    return "INTEGRATION_TOKEN"


def test_ws_stream_enqueues_hq_uploads_and_sends_signal_frames():
    token = _setup_receiver_for_integration()
    client = TestClient(server.app)
    with client.websocket_connect(
        f"/ws/stream?token={token}&frequency_hz=145000000&duration_seconds=1"
    ) as ws:
        msg = ws.receive_json()
        assert msg.get("type") == "signal"
        assert msg.get("decoded_text") == "HELLO"

    # After the stream, the receiver should have queued at least one upload packet for HQ.
    receiver: server.ReceiverService = server.app.state.receiver
    q = receiver._upload_queue
    assert not q.empty()
    packet = q.get_nowait()
    assert packet["decoded_text"] == "HELLO"

