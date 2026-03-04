"""Injection endpoints for demo: push messages (and optional audio) into the RX path."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from radioshaq.api.dependencies import get_current_user
from radioshaq.auth.jwt import TokenPayload
from radioshaq.radio.injection import get_injection_queue

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
    request: Request,
    body: InjectMessageBody,
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Inject a message into the RX path for demo/testing.

    The message will be available to receivers (radio_rx / digital_modes)
    when they poll the injection queue. Unless inject_skip_bus is True,
    also publish to MessageBus so the orchestrator processes it.
    """
    from radioshaq.api.dependencies import get_config
    from radioshaq.orchestrator.radio_ingestion import radio_received_to_inbound

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
    config = get_config(request)
    if not getattr(config.radio, "inject_skip_bus", False):
        bus = getattr(request.app.state, "message_bus", None)
        if bus and hasattr(bus, "publish_inbound"):
            inbound = radio_received_to_inbound(
                text=body.text,
                band=body.band,
                frequency_hz=body.frequency_hz,
                source_callsign=body.source_callsign,
                destination_callsign=body.destination_callsign,
                mode=body.mode,
            )
            await bus.publish_inbound(inbound)
    return {
        "ok": True,
        "message": "Injected",
        "qsize": queue.qsize(),
    }
