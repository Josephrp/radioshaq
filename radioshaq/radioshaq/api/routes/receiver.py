"""Receiver upload endpoint: remote receiver stations POST data to HQ."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from radioshaq.api.dependencies import get_config, get_current_user, get_transcript_storage
from radioshaq.auth.jwt import TokenPayload
from radioshaq.radio.bands import get_band_for_frequency
from radioshaq.radio.injection import get_injection_queue

router = APIRouter()


class ReceiverUploadBody(BaseModel):
    """Payload from a remote receiver station (SDR samples/decoded data)."""

    station_id: str = Field(..., description="Receiver station ID")
    operator_id: str = Field(..., description="Operator/sub from JWT")
    timestamp: str = Field(..., description="ISO timestamp")
    frequency_hz: float = Field(..., description="Frequency in Hz")
    signal_strength_db: float = Field(..., description="Signal strength dB")
    decoded_text: str | None = Field(None, description="Decoded text if any")
    mode: str = Field("", description="Mode (e.g. FM, FT8)")


@router.post("/upload")
async def receiver_upload(
    request: Request,
    body: ReceiverUploadBody,
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, str | int]:
    """
    Accept upload from a remote receiver station.

    Called by radioshaq.remote_receiver (SDR service) when HQ_URL points here.
    Requires Bearer JWT. When receiver_upload_store is enabled, persists transcript
    with band (from frequency). When receiver_upload_inject is enabled, injects
    into the RX path after store.
    """
    config = get_config(request)
    radio_cfg = config.radio
    band = get_band_for_frequency(body.frequency_hz) if body.frequency_hz else None
    transcript_id: int | None = None

    if radio_cfg.receiver_upload_store:
        storage = get_transcript_storage(request)
        if storage:
            session_id = f"receiver-{body.station_id}-{body.timestamp}"
            metadata = {
                "band": band or "unknown",
                "source": "receiver_upload",
                "signal_strength_db": body.signal_strength_db,
            }
            transcript_id = await storage.store(
                session_id=session_id,
                source_callsign=body.station_id or "RECV",
                frequency_hz=body.frequency_hz,
                mode=body.mode or "FM",
                transcript_text=body.decoded_text or "",
                destination_callsign=None,
                metadata=metadata,
            )
    if radio_cfg.receiver_upload_inject:
        queue = get_injection_queue()
        queue.inject_message(
            text=body.decoded_text or "",
            band=band,
            frequency_hz=body.frequency_hz,
            mode=body.mode or "FM",
            source_callsign=body.station_id or "RECV",
            destination_callsign=None,
        )
    if not getattr(radio_cfg, "receiver_upload_skip_bus", False):
        bus = getattr(request.app.state, "message_bus", None)
        if bus and hasattr(bus, "publish_inbound"):
            from radioshaq.orchestrator.radio_ingestion import radio_received_to_inbound
            inbound = radio_received_to_inbound(
                text=body.decoded_text or "",
                band=band,
                frequency_hz=body.frequency_hz,
                source_callsign=body.station_id or "RECV",
                destination_callsign=None,
                mode=body.mode or "FM",
            )
            await bus.publish_inbound(inbound)

    out: dict[str, str | int] = {"status": "ok", "received": body.station_id}
    if transcript_id is not None:
        out["transcript_id"] = transcript_id
    return out
