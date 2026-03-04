"""Receiver upload endpoint: remote receiver stations POST data to HQ."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from radioshaq.api.dependencies import get_current_user
from radioshaq.auth.jwt import TokenPayload

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
    body: ReceiverUploadBody,
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, str]:
    """
    Accept upload from a remote receiver station.

    Called by radioshaq.remote_receiver (SDR service) when HQ_URL points here.
    Requires Bearer JWT. Payload can be stored or forwarded (e.g. to injection queue).
    """
    # TODO: optionally persist to DB or push to injection queue
    return {"status": "ok", "received": body.station_id}
