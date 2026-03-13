"""Remote receiver FastAPI app and WebSocket stream."""

from __future__ import annotations

import asyncio
import base64
import os
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable

import numpy as np
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from loguru import logger

from radioshaq.radio.hackrf_tx_compat import stream_hackrf_iq_bytes
from radioshaq.remote_receiver.auth import JWTReceiverAuth
from radioshaq.remote_receiver.hq_client import HQClient
from radioshaq.remote_receiver.radio_interface import (
    SDRInterface,
    SignalSample,
    create_sdr_from_env,
)


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
    def from_env(cls, *, broker: Any | None = None, device_manager: Any | None = None) -> "ReceiverService":
        """Build from environment."""
        secret = os.environ.get("JWT_SECRET", "")
        station_id = os.environ.get("STATION_ID", "RECEIVER")
        jwt_auth = JWTReceiverAuth(secret=secret)
        radio = create_sdr_from_env(device_manager=device_manager, broker=broker)
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
                logger.warning("Upload loop error: {}", e)
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


class HackRFDeviceManager:
    """
    Own a single pyhackrf2.HackRF instance within the receiver process.

    All direct calls into libhackrf should happen underneath this manager,
    coordinated via an asyncio.Lock to ensure single-owner semantics.
    """

    def __init__(
        self,
        device_index: int,
        serial_number: str | None,
        max_gain: int,
        restricted_region: str,
    ):
        self._device_index = device_index
        self._serial_number = serial_number
        self._max_gain = max(0, min(47, max_gain))
        self._restricted_region = restricted_region
        self._device: Any | None = None
        self._lock = asyncio.Lock()

    @property
    def max_gain(self) -> int:
        return self._max_gain

    @property
    def restricted_region(self) -> str:
        return self._restricted_region

    def _open_device(self) -> Any:
        """Lazily open the underlying HackRF device."""
        if self._device is not None:
            return self._device
        try:
            from pyhackrf2 import HackRF

            if self._serial_number:
                self._device = HackRF(serial_number=self._serial_number)
            else:
                self._device = HackRF(device_index=self._device_index)
            return self._device
        except ImportError as e:
            raise RuntimeError(
                "HackRF device manager requires pyhackrf2. "
                "Install with: uv sync --extra hackrf (or pip install pyhackrf2)"
            ) from e
        except Exception as e:  # pragma: no cover - hardware/driver dependent
            raise RuntimeError(f"HackRF open failed: {e!r}") from e

    async def with_device(self, fn: Callable[[Any], Awaitable[Any]]) -> Any:
        """
        Run an async function with exclusive access to the HackRF device.

        The callback receives the underlying pyhackrf2.HackRF instance.
        """
        async with self._lock:
            dev = self._open_device()
            return await fn(dev)


class HackRFBroker:
    """Coordinate HackRF TX (and later RX) behind a single async interface."""

    def __init__(self, device_manager: HackRFDeviceManager | None) -> None:
        self._dm = device_manager
        self._lock = asyncio.Lock()
        self._stop_rx = asyncio.Event()
        self._rx_active = asyncio.Event()

    @property
    def lock(self) -> asyncio.Lock:
        """Global HackRF scheduling lock (RX and TX share this)."""
        return self._lock

    @property
    def available(self) -> bool:
        return self._dm is not None

    def request_tx(self) -> None:
        """Signal that TX work is about to start; RX loops should wind down."""
        self._stop_rx.set()

    def clear_tx(self) -> None:
        """Clear TX request flag after TX has completed."""
        self._stop_rx.clear()

    @property
    def should_stop_rx(self) -> bool:
        """True when RX loops should stop promptly to yield to TX."""
        return self._stop_rx.is_set()

    @property
    def rx_active(self) -> asyncio.Event:
        """Event that is set while an RX loop is active (backend-controlled)."""
        return self._rx_active

    async def tx_tone(
        self,
        *,
        frequency_hz: float,
        duration_sec: float,
        sample_rate: int = 2_000_000,
    ) -> None:
        if self._dm is None:
            raise RuntimeError("HackRF TX is not configured on this receiver")
        loop = asyncio.get_running_loop()

        async def _fn(dev: Any) -> None:
            # Generate a simple tone in int8 interleaved I/Q, matching HackRF expectations.
            tone_hz = 1000.0
            num_samples = int(duration_sec * sample_rate)
            t = np.arange(num_samples, dtype=np.float64) / sample_rate
            i = (127 * 0.3 * np.cos(2 * np.pi * tone_hz * t)).astype(np.int8)
            q = (127 * 0.3 * np.sin(2 * np.pi * tone_hz * t)).astype(np.int8)
            iq = np.empty(2 * num_samples, dtype=np.int8)
            iq[0::2] = i
            iq[1::2] = q

            def _blocking_tx() -> None:
                try:
                    dev.center_freq = int(frequency_hz)
                    dev.sample_rate = sample_rate
                    try:
                        dev.txvga_gain = self._dm.max_gain
                    except AttributeError:
                        pass
                except AttributeError:
                    # Older or stub objects may not expose these attributes.
                    pass
                try:
                    buf = iq.tobytes()
                    stream_hackrf_iq_bytes(dev, buf, duration_sec)
                except (AttributeError, TypeError, RuntimeError) as e:
                    logger.warning("HackRF TX not available ({}); tone TX skipped", repr(e))

            await loop.run_in_executor(None, _blocking_tx)

        async with self._lock:
            await self._dm.with_device(_fn)

    async def tx_iq(
        self,
        *,
        frequency_hz: float,
        sample_rate: int,
        iq_bytes: bytes,
        occupied_bandwidth_hz: float | None = None,
    ) -> None:
        if self._dm is None:
            raise RuntimeError("HackRF TX is not configured on this receiver")
        loop = asyncio.get_running_loop()
        iq = np.frombuffer(iq_bytes, dtype=np.int8)

        async def _fn(dev: Any) -> None:
            def _blocking_tx() -> None:
                try:
                    dev.center_freq = int(frequency_hz)
                    dev.sample_rate = sample_rate
                    try:
                        dev.txvga_gain = self._dm.max_gain
                    except AttributeError:
                        pass
                except AttributeError:
                    # Older or stub objects may not expose these attributes.
                    pass
                try:
                    buf = iq.tobytes()
                    duration_sec = len(buf) / (2.0 * sample_rate)
                    stream_hackrf_iq_bytes(dev, buf, duration_sec)
                except (AttributeError, TypeError, RuntimeError) as e:
                    logger.warning("HackRF TX not available ({}); IQ TX skipped", repr(e))

            await loop.run_in_executor(None, _blocking_tx)

        async with self._lock:
            await self._dm.with_device(_fn)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start receiver service."""
    # Optional HackRF TX broker and device manager: only when SDR_TYPE=hackrf.
    broker: HackRFBroker | None
    device_manager: HackRFDeviceManager | None = None
    sdr_type = os.environ.get("SDR_TYPE", "rtlsdr").strip().lower()
    if sdr_type != "hackrf":
        broker = None
    else:
        try:
            index = int(os.environ.get("HACKRF_INDEX", "0"))
            serial = os.environ.get("HACKRF_SERIAL") or None
            max_gain = int(os.environ.get("HACKRF_MAX_GAIN", "47"))
            restricted_region = os.environ.get("RESTRICTED_BANDS_REGION", "FCC")
            device_manager = HackRFDeviceManager(
                device_index=index,
                serial_number=serial,
                max_gain=max_gain,
                restricted_region=restricted_region,
            )
            broker = HackRFBroker(device_manager=device_manager)
        except Exception as e:
            logger.warning("HackRF broker TX not available: {}", repr(e))
            broker = HackRFBroker(device_manager=None)
            device_manager = None
    service = ReceiverService.from_env(broker=broker, device_manager=device_manager)
    app.state.receiver = service
    app.state.hackrf_broker = broker
    await service.start()
    yield
    # Shutdown


app = FastAPI(title="RadioShaq Remote Receiver", lifespan=lifespan)


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """Stream SDR output. Query params: token, frequency_hz, duration_seconds."""
    token = websocket.query_params.get("token", "")
    frequency_hz = float(websocket.query_params.get("frequency_hz", "145000000"))
    duration_seconds = int(websocket.query_params.get("duration_seconds", "60"))
    mode = websocket.query_params.get("mode")
    audio_rate_hz = websocket.query_params.get("audio_rate_hz")
    bfo_hz = websocket.query_params.get("bfo_hz")
    audio_rate = int(audio_rate_hz) if audio_rate_hz else None
    bfo = float(bfo_hz) if bfo_hz else None
    receiver: ReceiverService = websocket.app.state.receiver
    # HackRF RX/TX scheduling is now managed inside the backend via the shared
    # HackRFDeviceManager and HackRFBroker flags; no broad websocket lock.
    await receiver.stream_frequency(
        frequency_hz=frequency_hz,
        duration_seconds=duration_seconds,
        websocket=websocket,
        token=token,
        mode=mode,
        audio_rate_hz=audio_rate,
        bfo_hz=bfo,
    )


async def _require_broker_auth(request: Request) -> None:
    """Simple auth for TX endpoints: reuse JWTReceiverAuth with bearer or query token."""
    token = ""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    if not token:
        token = request.query_params.get("token", "")
    receiver: ReceiverService = request.app.state.receiver
    if not token:
        raise HTTPException(status_code=401, detail="Missing authorization token for HackRF TX")
    try:
        await receiver.jwt_auth.verify_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authorization token for HackRF TX")


@app.post("/tx/tone")
async def tx_tone(request: Request) -> dict[str, Any]:
    """Transmit a short tone via the HackRF broker.

    Body: {\"frequency_hz\": float, \"duration_sec\": float, \"sample_rate\": int }
    """
    await _require_broker_auth(request)
    body = await request.json()
    try:
        frequency_hz = float(body.get("frequency_hz"))
        duration_sec = float(body.get("duration_sec", 1.0))
        sample_rate = int(body.get("sample_rate", 2_000_000))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid TX tone payload: {e}")
    broker: HackRFBroker | None = request.app.state.hackrf_broker
    if broker is None or not broker.available:
        raise HTTPException(status_code=503, detail="HackRF TX broker not available")
    try:
        broker.request_tx()
        await broker.tx_tone(
            frequency_hz=frequency_hz,
            duration_sec=duration_sec,
            sample_rate=sample_rate,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.warning("HackRF TX tone error: {}", repr(e))
        raise HTTPException(status_code=500, detail="HackRF TX tone failed")
    finally:
        broker.clear_tx()
    return {"success": True, "notes": "HackRF tone transmitted via remote receiver"}


@app.post("/tx/iq")
async def tx_iq(request: Request) -> dict[str, Any]:
    """Transmit I/Q samples via the HackRF broker.

    Body: {\"frequency_hz\": float, \"sample_rate\": int, \"iq_b64\": str, \"occupied_bandwidth_hz\": float | null }
    """
    await _require_broker_auth(request)
    body = await request.json()
    try:
        frequency_hz = float(body.get("frequency_hz"))
        sample_rate = int(body.get("sample_rate"))
        iq_b64 = body.get("iq_b64")
        if not isinstance(iq_b64, str):
            raise ValueError("iq_b64 must be a base64-encoded string")
        occupied_bandwidth_hz_raw = body.get("occupied_bandwidth_hz")
        occupied_bandwidth_hz = (
            float(occupied_bandwidth_hz_raw) if occupied_bandwidth_hz_raw is not None else None
        )
        iq_bytes = base64.b64decode(iq_b64.encode("ascii"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid TX IQ payload: {e}")
    broker: HackRFBroker | None = request.app.state.hackrf_broker
    if broker is None or not broker.available:
        raise HTTPException(status_code=503, detail="HackRF TX broker not available")
    try:
        broker.request_tx()
        await broker.tx_iq(
            frequency_hz=frequency_hz,
            sample_rate=sample_rate,
            iq_bytes=iq_bytes,
            occupied_bandwidth_hz=occupied_bandwidth_hz,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.warning("HackRF TX IQ error: {}", repr(e))
        raise HTTPException(status_code=500, detail="HackRF TX IQ failed")
    finally:
        broker.clear_tx()
    return {"success": True, "notes": "HackRF IQ transmitted via remote receiver"}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tx/status")
async def tx_status() -> dict[str, Any]:
    """Report HackRF TX broker availability for this receiver process."""
    broker: HackRFBroker | None = app.state.hackrf_broker
    if broker is None or not broker.available:
        return {"available": False, "reason": "hackrf_tx_not_configured"}
    return {"available": True, "reason": "ok"}


def main() -> None:
    """Entry point for `radioshaq run-receiver` (uvicorn)."""
    import uvicorn
    host = os.environ.get("RECEIVER_HOST", "0.0.0.0")
    port = int(os.environ.get("RECEIVER_PORT", "8765"))
    uvicorn.run(
        "radioshaq.remote_receiver.server:app",
        host=host,
        port=port,
    )
