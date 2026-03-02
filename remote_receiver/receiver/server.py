"""Remote receiver FastAPI app and WebSocket stream."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from loguru import logger

from receiver.auth import JWTReceiverAuth
from receiver.hq_client import HQClient
from receiver.radio_interface import SDRInterface, SignalSample


class ReceiverService:
    """Remote receiver: SDR, JWT auth, HQ upload."""

    def __init__(
        self,
        station_id: str,
        jwt_auth: JWTReceiverAuth,
        radio: SDRInterface,
        hq_client: HQClient | None,
    ):
        self.station_id = station_id
        self.jwt_auth = jwt_auth
        self.radio = radio
        self.hq = hq_client
        self._upload_queue: asyncio.Queue[dict[str, Any]] = (
            hq_client.upload_queue if hq_client else asyncio.Queue()
        )

    @classmethod
    def from_env(cls) -> "ReceiverService":
        """Build from environment."""
        secret = os.environ.get("JWT_SECRET", "")
        station_id = os.environ.get("STATION_ID", "RECEIVER")
        jwt_auth = JWTReceiverAuth(secret=secret)
        radio = SDRInterface(
            device_index=int(os.environ.get("RTLSDR_INDEX", "0")),
        )
        hq_url = os.environ.get("HQ_URL")
        hq_token = os.environ.get("HQ_TOKEN", "")
        hq_client = HQClient(hq_url or "http://localhost:8000", hq_token, station_id) if hq_url else None
        return cls(station_id=station_id, jwt_auth=jwt_auth, radio=radio, hq_client=hq_client)

    async def start(self) -> None:
        """Initialize radio and HQ."""
        await self.radio.initialize()
        if self.hq:
            await self.hq.connect()
        asyncio.create_task(self._upload_loop())

    async def _upload_loop(self) -> None:
        """Process upload queue to HQ."""
        if not self.hq:
            return
        while True:
            try:
                packet = await self._upload_queue.get()
                await self.hq.upload(packet)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Upload loop error: %s", e)
            await asyncio.sleep(0.1)

    async def _queue_for_hq(self, signal: SignalSample, operator_id: str) -> None:
        """Queue signal for HQ upload."""
        packet = {
            "station_id": self.station_id,
            "operator_id": operator_id,
            "timestamp": signal.timestamp.isoformat(),
            "frequency_hz": signal.frequency_hz,
            "signal_strength_db": signal.strength_db,
            "decoded_text": signal.decoded_data,
            "mode": signal.mode,
        }
        await self._upload_queue.put(packet)

    async def stream_frequency(
        self,
        frequency_hz: float,
        duration_seconds: int,
        websocket: WebSocket,
        token: str,
    ) -> None:
        """WebSocket: verify JWT, tune, stream samples."""
        payload = await self.jwt_auth.verify_token(token)
        await websocket.accept()
        try:
            await self.radio.set_frequency(frequency_hz)
            async for signal in self.radio.receive(float(duration_seconds)):
                await websocket.send_json({
                    "type": "signal",
                    "timestamp": signal.timestamp.isoformat(),
                    "signal_strength": signal.strength_db,
                    "decoded": signal.decoded_data,
                })
                await self._queue_for_hq(signal, payload.sub)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            await websocket.send_json({"type": "error", "message": str(e)})
        finally:
            try:
                await websocket.close()
            except Exception:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start receiver service."""
    service = ReceiverService.from_env()
    app.state.receiver = service
    await service.start()
    yield
    # Shutdown


app = FastAPI(title="SHAKODS Remote Receiver", lifespan=lifespan)


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """Stream SDR output. Query params: token, frequency_hz, duration_seconds."""
    token = websocket.query_params.get("token", "")
    frequency_hz = float(websocket.query_params.get("frequency_hz", "145000000"))
    duration_seconds = int(websocket.query_params.get("duration_seconds", "60"))
    receiver: ReceiverService = websocket.app.state.receiver
    await receiver.stream_frequency(
        frequency_hz=frequency_hz,
        duration_seconds=duration_seconds,
        websocket=websocket,
        token=token,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
