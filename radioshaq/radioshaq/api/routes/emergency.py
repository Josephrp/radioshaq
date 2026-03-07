"""Emergency coordination events: request and approve (§9)."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from radioshaq.api.dependencies import get_config, get_current_user
from radioshaq.auth.jwt import TokenPayload
from radioshaq.config.schema import Config
from radioshaq.messaging_compliance import emergency_messaging_allowed

router = APIRouter()

E164_PATTERN = re.compile(r"^\+?[0-9]{10,15}$")


def _normalize_e164(phone: str) -> str:
    digits = re.sub(r"\D", "", (phone or "").strip())
    return "+" + digits if digits else ""


class EmergencyRequestBody(BaseModel):
    """Body for POST /emergency/request."""

    target_callsign: str | None = Field(None, description="Target callsign (optional)")
    contact_phone: str = Field(..., description="Contact phone E.164 for SMS/WhatsApp")
    contact_channel: str = Field(..., description="sms or whatsapp")
    notes: str | None = Field(None)


class ApproveBody(BaseModel):
    """Body for POST /emergency/events/{id}/approve."""

    notes: str | None = Field(None)


class RejectBody(BaseModel):
    """Body for POST /emergency/events/{id}/reject."""

    notes: str | None = Field(None)


@router.post("/request")
async def create_emergency_request(
    request: Request,
    body: EmergencyRequestBody,
    config: Config = Depends(get_config),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Create an emergency coordination event (status=pending). Only allowed when
    emergency_contact is enabled and current region is in regions_allowed.
    """
    region = getattr(config.radio, "restricted_bands_region", None) or ""
    if not emergency_messaging_allowed(region, getattr(config, "emergency_contact", None)):
        raise HTTPException(
            status_code=403,
            detail="Emergency SMS/WhatsApp not allowed in this region",
        )
    if body.contact_channel not in ("sms", "whatsapp"):
        raise HTTPException(status_code=400, detail="contact_channel must be sms or whatsapp")
    phone = _normalize_e164(body.contact_phone)
    if not E164_PATTERN.match(phone):
        raise HTTPException(status_code=400, detail="contact_phone must be E.164 (10–15 digits)")
    initiator = getattr(_user, "callsign", None) or getattr(_user, "sub", "api")
    if isinstance(initiator, str) and len(initiator) > 20:
        initiator = "api"
    db = getattr(request.app.state, "db", None)
    if db is None or not hasattr(db, "store_coordination_event"):
        raise HTTPException(status_code=503, detail="Database not available")
    extra = {
        "emergency_contact_phone": phone,
        "emergency_contact_channel": body.contact_channel,
    }
    event_id = await db.store_coordination_event(
        event_type="emergency",
        initiator_callsign=initiator,
        target_callsign=body.target_callsign.strip().upper() if body.target_callsign else None,
        status="pending",
        priority=1,
        notes=body.notes,
        extra_data=extra,
    )
    return {"ok": True, "event_id": event_id, "status": "pending"}


async def _get_pending_emergency_count(request: Request) -> int:
    """Return number of pending emergency events (for use by pending-count and SSE stream)."""
    db = getattr(request.app.state, "db", None)
    if db is None or not hasattr(db, "get_pending_coordination_events"):
        return 0
    events = await db.get_pending_coordination_events(max_results=1000, event_type="emergency")
    return len(events)


@router.get("/pending-count")
async def emergency_pending_count(
    request: Request,
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Return the number of pending emergency events. Use this to inform the operator
    (e.g. dashboard polling or script) that action is required; then list with GET /emergency/events.
    """
    count = await _get_pending_emergency_count(request)
    return {"count": count}


async def _emergency_stream_generator(request: Request) -> AsyncIterator[str]:
    """SSE: send pending_count every 10s so the operator UI can show alerts without polling."""
    interval = 10.0
    while True:
        try:
            count = await _get_pending_emergency_count(request)
            payload = json.dumps({"pending_count": count})
            yield f"data: {payload}\n\n"
        except asyncio.CancelledError:
            break
        except Exception:
            yield f"data: {json.dumps({'pending_count': 0, 'error': True})}\n\n"
        await asyncio.sleep(interval)


@router.get("/events/stream")
async def emergency_events_stream(
    request: Request,
    _user: TokenPayload = Depends(get_current_user),
) -> StreamingResponse:
    """
    Server-Sent Events stream of pending emergency count. Send event every 10s.
    Operator UI can subscribe to trigger audio and browser notifications when count > 0.
    """
    return StreamingResponse(
        _emergency_stream_generator(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/events")
async def list_emergency_events(
    request: Request,
    status: str | None = None,
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """List coordination events with event_type=emergency. Optional filter by status."""
    db = getattr(request.app.state, "db", None)
    if db is None or not hasattr(db, "get_pending_coordination_events"):
        return {"events": [], "count": 0}
    events = await db.get_pending_coordination_events(max_results=1000, event_type="emergency")
    if status:
        events = [e for e in events if e.get("status") == status]
    return {"events": events, "count": len(events)}


@router.post("/events/{event_id:int}/approve")
async def approve_emergency_event(
    request: Request,
    event_id: int,
    body: ApproveBody,
    config: Config = Depends(get_config),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Approve an emergency event and send the SMS/WhatsApp. Sets status=approved,
    records approved_at and approved_by, publishes OutboundMessage, then sets sent_at.
    """
    region = getattr(config.radio, "restricted_bands_region", None) or ""
    if not emergency_messaging_allowed(region, getattr(config, "emergency_contact", None)):
        raise HTTPException(status_code=403, detail="Emergency SMS/WhatsApp not allowed in this region")
    db = getattr(request.app.state, "db", None)
    if db is None or not hasattr(db, "get_coordination_event_by_id") or not hasattr(db, "update_coordination_event"):
        raise HTTPException(status_code=503, detail="Database not available")
    event = await db.get_coordination_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.get("event_type") != "emergency":
        raise HTTPException(status_code=400, detail="Not an emergency event")
    if event.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Event already processed")
    extra = event.get("extra_data") or {}
    if extra.get("sent_at"):
        raise HTTPException(status_code=400, detail="Already sent")
    phone = extra.get("emergency_contact_phone")
    channel = extra.get("emergency_contact_channel")
    if not phone or channel not in ("sms", "whatsapp"):
        raise HTTPException(status_code=400, detail="Missing contact_phone or contact_channel")
    approver = getattr(_user, "sub", None) or getattr(_user, "callsign", "api")
    now = datetime.now(timezone.utc).isoformat()
    message_bus = getattr(request.app.state, "message_bus", None)
    if not message_bus or not hasattr(message_bus, "publish_outbound"):
        return {"ok": True, "event_id": event_id, "status": "pending", "sent": False, "detail": "Message bus not available"}
    from radioshaq.vendor.nanobot.bus.events import OutboundMessage
    content = extra.get("message") or event.get("notes") or "Emergency notification from RadioShaq."
    ok = await message_bus.publish_outbound(
        OutboundMessage(
            channel=channel,
            chat_id=phone,
            content=content,
            reply_to=None,
            media=[],
            metadata={"emergency_event_id": event_id, "approved_by": str(approver)},
        )
    )
    if not ok:
        return {"ok": True, "event_id": event_id, "status": "pending", "sent": False, "detail": "Outbound queue full"}
    await db.update_coordination_event(
        event_id,
        status="approved",
        extra_data={
            "approved_at": now,
            "approved_by": str(approver),
            "sent_at": now,
            **({"notes": body.notes} if body.notes else {}),
        },
    )
    return {"ok": True, "event_id": event_id, "status": "approved", "sent": True}


@router.post("/events/{event_id:int}/reject")
async def reject_emergency_event(
    request: Request,
    event_id: int,
    body: RejectBody,
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Reject an emergency event (do not send). Sets status=rejected and records rejected_at, rejected_by."""
    db = getattr(request.app.state, "db", None)
    if db is None or not hasattr(db, "get_coordination_event_by_id") or not hasattr(db, "update_coordination_event"):
        raise HTTPException(status_code=503, detail="Database not available")
    event = await db.get_coordination_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.get("event_type") != "emergency":
        raise HTTPException(status_code=400, detail="Not an emergency event")
    if event.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Event already processed")
    rejector = getattr(_user, "sub", None) or getattr(_user, "callsign", "api")
    now = datetime.now(timezone.utc).isoformat()
    extra = event.get("extra_data") or {}
    extra.update({"rejected_at": now, "rejected_by": str(rejector), **({"notes": body.notes} if body.notes else {})})
    await db.update_coordination_event(event_id, status="rejected", extra_data=extra)
    return {"ok": True, "event_id": event_id, "status": "rejected"}
