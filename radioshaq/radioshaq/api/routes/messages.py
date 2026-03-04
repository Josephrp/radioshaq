"""Message and orchestrator request endpoints.

Request body may include InboundMessage-compatible fields for outbound routing:
- message or text: required, content to process
- channel: optional (e.g. whatsapp, sms, api), for future OutboundMessage routing
- chat_id: optional, for future OutboundMessage routing
- sender_id: optional, for logging/context
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field as PydanticField

from radioshaq.api.callsign_whitelist import get_effective_allowed_callsigns, is_callsign_allowed
from radioshaq.api.dependencies import (
    get_config,
    get_current_user,
    get_orchestrator,
    get_radio_tx_agent,
    get_transcript_storage,
)
from radioshaq.auth.jwt import TokenPayload
from radioshaq.radio.bands import BAND_PLANS
from radioshaq.radio.injection import get_injection_queue

router = APIRouter()

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/process")
async def process_message(
    body: dict[str, Any],
    user: TokenPayload = Depends(get_current_user),
    orchestrator: Any = Depends(get_orchestrator),
) -> dict[str, Any]:
    """
    Submit a message for REACT orchestration.
    Requires orchestrator to be set in app state (lifespan).
    Optional body fields: channel, chat_id, sender_id (InboundMessage shape for routing).
    """
    if not orchestrator:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not available",
        )
    request_text = body.get("message", body.get("text", ""))
    if not request_text:
        raise HTTPException(status_code=400, detail="message or text required")
    callsign = body.get("sender_id") or body.get("callsign")
    if callsign is None and user:
        callsign = getattr(user, "station_id", None) or getattr(user, "sub", None)
    if callsign is not None:
        callsign = str(callsign).strip().upper() or None
    result = await orchestrator.process_request(request=request_text, callsign=callsign)
    response: dict[str, Any] = {
        "success": result.success,
        "message": result.message,
        "task_id": result.state.task_id,
    }
    if body.get("channel") is not None:
        response["channel"] = body["channel"]
    if body.get("chat_id") is not None:
        response["chat_id"] = body["chat_id"]
    return response


@router.post("/whitelist-request")
async def whitelist_request(
    request: Request,
    user: TokenPayload = Depends(get_current_user),
    orchestrator: Any = Depends(get_orchestrator),
    radio_tx_agent: Any = Depends(get_radio_tx_agent),
) -> dict[str, Any]:
    """
    Whitelist entry point: request access to gated services (e.g. messaging between bands).
    Text or audio → orchestrator evaluates → response as text and optionally TTS.
    Accepts application/json: { "text" or "message", "callsign?", "send_audio_back?" }
    or multipart/form-data: file (audio), callsign, send_audio_back.

    Approved/message can come from either the orchestrator final message (tool path:
    LLM used register_callsign tool and replied) or a completed whitelist agent task
    (agent path: ACTING ran the whitelist agent; result in completed_tasks).
    """
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Orchestrator not available")

    request_text = None
    callsign: str | None = None
    send_audio_back = True
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()

    if content_type == "application/json":
        try:
            body = await request.json()
        except Exception:
            body = {}
        request_text = body.get("text") or body.get("message")
        callsign = body.get("callsign")
        if "send_audio_back" in body:
            send_audio_back = bool(body["send_audio_back"])
    elif content_type == "multipart/form-data":
        form = await request.form()
        request_text = form.get("text") or form.get("message")
        if request_text and isinstance(request_text, UploadFile):
            request_text = (await request_text.read()).decode("utf-8", errors="replace")
        callsign = form.get("callsign")
        if callsign and hasattr(callsign, "strip"):
            callsign = str(callsign).strip() or None
        elif callable(getattr(callsign, "strip", None)):
            callsign = str(callsign).strip() or None
        if "send_audio_back" in form:
            send_audio_back = str(form["send_audio_back"]).strip().lower() in ("1", "true", "yes")
        if not request_text and "file" in form:
            file = form["file"]
            if hasattr(file, "read") and file.filename:
                content = await file.read()
                if len(content) > MAX_AUDIO_BYTES:
                    raise HTTPException(status_code=400, detail="File too large")
                if not getattr(file, "content_type", None) or not (
                    (file.content_type or "").startswith("audio/")
                    or file.content_type == "application/octet-stream"
                ):
                    raise HTTPException(status_code=400, detail="Expected audio file")
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(content)
                    temp_path = f.name
                try:
                    from radioshaq.audio.asr import transcribe_audio_voxtral
                    request_text = await asyncio.to_thread(transcribe_audio_voxtral, temp_path, language="en")
                except ImportError:
                    raise HTTPException(status_code=503, detail="ASR not available")
                finally:
                    Path(temp_path).unlink(missing_ok=True)
                request_text = (request_text or "").strip()
    else:
        raise HTTPException(
            status_code=400,
            detail="Content-Type must be application/json or multipart/form-data",
        )

    if not request_text or not str(request_text).strip():
        raise HTTPException(status_code=400, detail="text, message, or audio file with speech required")
    request_text = str(request_text).strip()
    if callsign is not None:
        callsign = str(callsign).strip() or None

    orchestrator_input = f"User requests to be whitelisted for gated services (e.g. messaging between bands). Their message: {request_text}"
    if callsign:
        orchestrator_input += f" Stated callsign: {callsign}."

    result = await orchestrator.process_request(request=orchestrator_input, callsign=callsign)
    message_for_user = result.message

    approved_from_agent = None
    for task in result.state.completed_tasks:
        if getattr(task, "agent", None) == "whitelist" and task.result and isinstance(task.result, dict):
            approved_from_agent = task.result.get("approved")
            if message_for_user is None or message_for_user == "Incomplete":
                message_for_user = task.result.get("message_for_user") or task.result.get("reason")
            break

    audio_sent = False
    if send_audio_back and message_for_user and radio_tx_agent:
        tx_task = {
            "transmission_type": "voice",
            "message": message_for_user,
            "use_tts": True,
        }
        try:
            await radio_tx_agent.execute(tx_task, upstream_callback=None)
            audio_sent = True
        except Exception:
            pass

    return {
        "success": result.success,
        "message": message_for_user,
        "task_id": result.state.task_id,
        "approved": approved_from_agent,
        "audio_sent": audio_sent,
    }


@router.post("/from-audio")
async def message_from_audio(
    request: Request,
    file: UploadFile = File(...),
    source_callsign: str = Form(...),
    destination_callsign: str | None = Form(None),
    band: str | None = Form(None),
    mode: str = Form("PSK31"),
    frequency_hz: float = Form(0.0),
    session_id: str | None = Form(None),
    inject: bool = Form(False),
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Upload audio; run ASR; whitelist check; store transcript. Optionally inject to RX queue."""
    if not file.content_type or not (
        file.content_type.startswith("audio/") or file.content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="Expected audio file")
    content = await file.read()
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail=f"File too large (max {MAX_AUDIO_BYTES // (1024*1024)} MB)")
    config = get_config(request)
    allowed = await get_effective_allowed_callsigns(getattr(request.app.state, "db", None), config.radio)
    src = (source_callsign or "").strip().upper()
    if not src:
        raise HTTPException(status_code=400, detail="source_callsign required")
    if not is_callsign_allowed(src, allowed, config.radio.callsign_registry_required):
        raise HTTPException(status_code=403, detail="Source callsign not allowed")
    dest = (destination_callsign or "").strip().upper() or None
    if dest and not is_callsign_allowed(dest, allowed, config.radio.callsign_registry_required):
        raise HTTPException(status_code=403, detail="Destination callsign not allowed")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(content)
        temp_path = f.name
    try:
        from radioshaq.audio.asr import transcribe_audio_voxtral
        transcript_text = await asyncio.to_thread(
            transcribe_audio_voxtral, temp_path, language="en"
        )
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="ASR not available (uv sync --extra audio)",
        )
    finally:
        Path(temp_path).unlink(missing_ok=True)

    transcript_text = (transcript_text or "").strip()
    if not transcript_text:
        raise HTTPException(status_code=400, detail="No speech detected in audio")

    storage = get_transcript_storage(request)
    db = getattr(request.app.state, "db", None)
    transcript_id = 0
    if storage and db:
        sid = session_id or f"from-audio-{uuid.uuid4().hex[:12]}"
        freq = frequency_hz
        if freq <= 0 and band and band in BAND_PLANS:
            plan = BAND_PLANS[band]
            freq = plan.freq_start_hz + (plan.freq_end_hz - plan.freq_start_hz) / 2
        mode_val = (BAND_PLANS[band].modes[0]) if band and band in BAND_PLANS else mode
        transcript_id = await storage.store(
            session_id=sid,
            source_callsign=src,
            frequency_hz=freq,
            mode=mode_val,
            transcript_text=transcript_text,
            destination_callsign=dest,
            metadata={"band": band, "source": "from_audio"},
        )
    if inject:
        queue = get_injection_queue()
        queue.inject_message(
            text=transcript_text,
            band=band,
            frequency_hz=frequency_hz if frequency_hz > 0 else 0,
            mode=mode,
            source_callsign=src,
            destination_callsign=dest,
        )
    return {
        "ok": True,
        "transcript_id": transcript_id,
        "transcript_text": transcript_text,
        "injected": inject,
    }


class InjectAndStoreBody(BaseModel):
    """Body for POST /messages/inject-and-store."""

    text: str = PydanticField(..., min_length=1)
    band: str | None = None
    frequency_hz: float = 0.0
    mode: str = "PSK31"
    source_callsign: str | None = None
    destination_callsign: str | None = None
    audio_path: str | None = None
    metadata: dict[str, Any] = PydanticField(default_factory=dict)


@router.post("/inject-and-store")
async def inject_and_store(
    request: Request,
    body: InjectAndStoreBody,
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Inject message into RX queue and store to DB (whitelist enforced)."""
    b = body
    config = get_config(request)
    allowed = await get_effective_allowed_callsigns(getattr(request.app.state, "db", None), config.radio)
    src = (b.source_callsign or "UNKNOWN").strip().upper()
    if not is_callsign_allowed(src, allowed, config.radio.callsign_registry_required):
        raise HTTPException(status_code=403, detail="Source callsign not allowed")
    dest = (b.destination_callsign or "").strip().upper() or None
    if dest and not is_callsign_allowed(dest, allowed, config.radio.callsign_registry_required):
        raise HTTPException(status_code=403, detail="Destination callsign not allowed")

    queue = get_injection_queue()
    queue.inject_message(
        text=b.text,
        band=b.band,
        frequency_hz=b.frequency_hz,
        mode=b.mode,
        source_callsign=b.source_callsign,
        destination_callsign=b.destination_callsign,
        audio_path=b.audio_path,
        metadata=b.metadata,
    )
    transcript_id = None
    storage = get_transcript_storage(request)
    if storage and getattr(storage, "_db", None):
        transcript_id = await storage.store(
            session_id=f"inject-store-{uuid.uuid4().hex[:12]}",
            source_callsign=src,
            frequency_hz=b.frequency_hz,
            mode=b.mode,
            transcript_text=b.text,
            destination_callsign=dest,
            metadata={**(b.metadata or {}), "source": "inject_and_store"},
            raw_audio_path=b.audio_path,
        )
    return {"ok": True, "transcript_id": transcript_id, "qsize": queue.qsize()}
