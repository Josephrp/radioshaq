"""Internal message bus endpoints (nanobot InboundMessage ingestion)."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

from shakods.vendor.nanobot.bus.events import InboundMessage

router = APIRouter()


@router.post("/bus/inbound")
async def publish_inbound(
    request: Request,
    body: dict[str, Any] = Body(..., embed=False),
) -> dict[str, Any]:
    """
    Accept an inbound message (e.g. from Lambda) and publish to MessageBus.
    Body: channel, sender_id, chat_id, content; optional media, metadata, session_key_override.
    Orchestrator consumer must be running elsewhere to process (e.g. run_inbound_consumer).
    """
    bus = getattr(request.app.state, "message_bus", None)
    if not bus:
        raise HTTPException(status_code=503, detail="Message bus not available")
    content = body.get("content", "")
    channel = body.get("channel", "api")
    sender_id = body.get("sender_id", "")
    chat_id = body.get("chat_id", "")
    ts = body.get("timestamp")
    if isinstance(ts, str):
        try:
            timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            timestamp = datetime.utcnow()
    else:
        timestamp = datetime.utcnow()
    msg = InboundMessage(
        channel=channel,
        sender_id=sender_id,
        chat_id=chat_id,
        content=content,
        timestamp=timestamp,
        media=list(body.get("media", [])),
        metadata=dict(body.get("metadata", {})),
        session_key_override=body.get("session_key_override"),
    )
    ok = await bus.publish_inbound(msg)
    if not ok:
        raise HTTPException(status_code=507, detail="Inbound queue full")
    return {"accepted": True, "channel": channel, "chat_id": chat_id}
