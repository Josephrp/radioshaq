"""Injection endpoints for demo: push messages (and optional audio) into the RX path."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from shakods.api.dependencies import get_current_user
from shakods.auth.jwt import TokenPayload
from shakods.radio.injection import get_injection_queue

router = APIRouter()


class InjectMessageBody(BaseModel):
    """Body for POST /inject/message (user injection for demo)."""

    text: str = Field(..., min_length=1, description="Message text to inject as received")
    band: str | None = Field(None, description="Band name (e.g. 40m, 2m)")
    frequency_hz: float = Field(0.0, description="Frequency in Hz")
    mode: str = Field("PSK31", description="Mode (PSK31, FT8, FM, etc.)")
    source_callsign: str | None = Field(None, description="Source callsign")
    destination_callsign: str | None = Field(None, description="Destination callsign")
    audio_path: str | None = Field(None, description="Optional path to audio file (stored with transcript)")
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/message")
async def inject_message(
    body: InjectMessageBody,
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Inject a message into the RX path for demo/testing.

    The message will be available to receivers (radio_rx / digital_modes)
    when they poll the injection queue. Use for:
    - User injection script (e.g. audio → text → this endpoint)
    - Simulating one user emitting on a band for another to receive
    """
    queue = get_injection_queue()
    queue.inject_message(
        text=body.text,
        band=body.band,
        frequency_hz=body.frequency_hz,
        mode=body.mode,
        source_callsign=body.source_callsign,
        destination_callsign=body.destination_callsign,
        audio_path=body.audio_path,
        metadata=body.metadata,
    )
    return {
        "ok": True,
        "message": "Injected",
        "qsize": queue.qsize(),
    }
