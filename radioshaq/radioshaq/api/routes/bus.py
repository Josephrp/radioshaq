"""Internal message bus endpoints (nanobot InboundMessage ingestion) and opt-out (§8.1)."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, Field

from radioshaq.vendor.nanobot.bus.events import InboundMessage

router = APIRouter()


class OptOutBody(BaseModel):
    """Body for POST /internal/opt-out. Used by webhook when user sends STOP."""

    callsign: str | None = Field(None, description="Callsign to opt out")
    phone: str | None = Field(None, description="Phone (E.164) to opt out; used if callsign not set")
    channel: str = Field(..., description="sms or whatsapp")


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
            timestamp = datetime.now(timezone.utc)
    else:
        timestamp = datetime.now(timezone.utc)
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


@router.post("/opt-out")
async def opt_out(
    request: Request,
    body: OptOutBody,
) -> dict[str, Any]:
    """
    Record opt-out for notify-on-relay (§8.1). Call when user sends STOP via SMS/WhatsApp.
    Provide either callsign or phone + channel (sms/whatsapp). Clears that contact and sets opt_out_at.
    """
    if body.channel not in ("sms", "whatsapp"):
        raise HTTPException(status_code=400, detail="channel must be sms or whatsapp")
    db = getattr(request.app.state, "db", None)
    if db is None or not hasattr(db, "record_opt_out"):
        raise HTTPException(status_code=503, detail="Database not available")
    if body.callsign and body.callsign.strip():
        normalized = body.callsign.strip().upper()
        updated = await db.record_opt_out(normalized, body.channel)
    elif body.phone and body.phone.strip():
        updated = await db.record_opt_out_by_phone(body.phone.strip(), body.channel)
    else:
        raise HTTPException(status_code=400, detail="Provide callsign or phone")
    return {"ok": True, "opted_out": updated}
