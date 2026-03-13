"""Twilio webhook handlers (SMS + WhatsApp).

Twilio delivers inbound messages as application/x-www-form-urlencoded. We validate the webhook
signature when `config.twilio.auth_token` is configured, then publish an InboundMessage to the
MessageBus so the orchestrator can handle it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from loguru import logger

from radioshaq.utils.phone import normalize_e164
from radioshaq.vendor.nanobot.bus.events import InboundMessage

router = APIRouter()

_OPTOUT_KEYWORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"}


def _normalized_channel_from_form(explicit_channel: str, form: dict[str, Any]) -> str:
    frm = str(form.get("From", "") or "")
    if frm.startswith("whatsapp:"):
        return "whatsapp"
    return explicit_channel


def _normalize_from_phone(form: dict[str, Any]) -> str:
    frm = str(form.get("From", "") or "")
    if frm.startswith("whatsapp:"):
        frm = frm[len("whatsapp:") :]
    return normalize_e164(frm) or frm.strip()


def _collect_media_urls(form: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    try:
        n = int(str(form.get("NumMedia", "0") or "0"))
    except ValueError:
        n = 0
    for i in range(max(0, n)):
        u = form.get(f"MediaUrl{i}")
        if u:
            urls.append(str(u))
    return urls


def _twilio_request_url_for_signature(request: Request) -> str:
    # Twilio signs the full URL it requested. When behind a proxy, starlette's request.url
    # may reflect internal scheme/host, so we honor common X-Forwarded-* headers.
    proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    host = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    if not proto and request.headers.get("x-forwarded-ssl", "").lower() == "on":
        proto = "https"
    if not proto:
        proto = request.url.scheme
    if not host:
        host = request.url.netloc
    return f"{proto}://{host}{request.url.path}"


def _validate_twilio_signature_if_configured(
    request: Request, form: dict[str, Any], channel: str
) -> bool:
    cfg = getattr(request.app.state, "config", None)
    twilio_cfg = getattr(cfg, "twilio", None) if cfg else None
    auth_token = getattr(twilio_cfg, "auth_token", None) if twilio_cfg else None
    signature = request.headers.get("x-twilio-signature")

    if not auth_token:
        logger.warning("Twilio webhook received but twilio.auth_token not configured (channel={})", channel)
        return False
    if not signature:
        raise HTTPException(status_code=403, detail="Missing X-Twilio-Signature")

    try:
        from twilio.request_validator import RequestValidator
    except Exception as e:  # pragma: no cover
        logger.warning("Twilio SDK missing; cannot validate signature: {}", e)
        return False

    url = _twilio_request_url_for_signature(request)
    # Twilio validator expects a plain dict of str->str values.
    params = {k: str(v) for k, v in form.items()}
    ok = RequestValidator(str(auth_token)).validate(url, params, signature)
    if not ok:
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
    return True


def _twiml_response(message: str | None = None) -> Response:
    try:
        from twilio.twiml.messaging_response import MessagingResponse
    except Exception:
        # Fallback: Twilio accepts empty 200s; but TwiML is preferred.
        return Response(content="", media_type="text/plain")

    r = MessagingResponse()
    if message:
        r.message(message)
    return Response(content=str(r), media_type="application/xml")


async def _handle_inbound(request: Request, explicit_channel: str) -> Response:
    bus = getattr(request.app.state, "message_bus", None)
    if not bus:
        raise HTTPException(status_code=503, detail="Message bus not available")

    form_obj = await request.form()
    form: dict[str, Any] = dict(form_obj)

    channel = _normalized_channel_from_form(explicit_channel, form)
    signature_validated = _validate_twilio_signature_if_configured(request, form, channel)

    from_phone = _normalize_from_phone(form)
    body = str(form.get("Body", "") or "").strip()
    msg_sid = str(form.get("MessageSid", "") or "").strip() or None
    to_val = str(form.get("To", "") or "").strip() or None

    media_urls = _collect_media_urls(form)
    metadata: dict[str, Any] = {
        "provider": "twilio",
        "twilio_message_sid": msg_sid,
        "to": to_val,
        "from_raw": str(form.get("From", "") or ""),
        "signature_validated": signature_validated,
    }

    # Opt-out handling (STOP): record directly if DB available, then acknowledge.
    if body.upper() in _OPTOUT_KEYWORDS:
        db = getattr(request.app.state, "db", None)
        if db is not None and hasattr(db, "record_opt_out_by_phone"):
            try:
                await db.record_opt_out_by_phone(from_phone, channel)
            except Exception as e:
                logger.warning("Opt-out record failed (channel={} phone={}): {}", channel, from_phone, e)
        return _twiml_response("You have been opted out. Reply START to re-subscribe.")

    inbound = InboundMessage(
        channel=channel,
        sender_id=from_phone,
        chat_id=from_phone,
        content=body,
        timestamp=datetime.now(timezone.utc),
        media=media_urls,
        metadata=metadata,
    )
    ok = await bus.publish_inbound(inbound)
    if not ok:
        raise HTTPException(status_code=507, detail="Inbound queue full")

    # Let the orchestrator respond via outbound dispatcher (no immediate auto-reply).
    return _twiml_response(None)


@router.post("/sms")
async def twilio_sms_webhook(request: Request) -> Response:
    """Inbound SMS webhook from Twilio."""
    return await _handle_inbound(request, explicit_channel="sms")


@router.post("/whatsapp")
async def twilio_whatsapp_webhook(request: Request) -> Response:
    """Inbound WhatsApp webhook from Twilio."""
    return await _handle_inbound(request, explicit_channel="whatsapp")

