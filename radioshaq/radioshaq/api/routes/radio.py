"""Radio and propagation endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field

from radioshaq.api.dependencies import get_config, get_current_user, get_radio_tx_agent
from radioshaq.auth.jwt import TokenPayload
from radioshaq.compliance_plugin import get_band_plan_source_for_config
from radioshaq.config.schema import Config
from radioshaq.database.gis import propagation_prediction

router = APIRouter()


class SendTTSBody(BaseModel):
    """Body for POST /radio/send-tts."""

    message: str = Field(..., min_length=1)
    frequency_hz: float | None = None
    mode: str | None = None


class SendAudioBody(BaseModel):
    """Body for POST /radio/send-audio (multipart with file)."""

    frequency_hz: float | None = None
    mode: str | None = None


@router.get("/propagation")
async def propagation(
    lat_origin: float = Query(..., description="Origin latitude"),
    lon_origin: float = Query(..., description="Origin longitude"),
    lat_dest: float = Query(..., description="Destination latitude"),
    lon_dest: float = Query(..., description="Destination longitude"),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Get propagation prediction between two points."""
    return propagation_prediction(lat_origin, lon_origin, lat_dest, lon_dest)


@router.get("/bands")
async def bands(
    config: Config = Depends(get_config),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, list[str]]:
    """List supported bands (from effective band plan for config region)."""
    radio = config.radio
    plans = get_band_plan_source_for_config(
        radio.restricted_bands_region,
        getattr(radio, "band_plan_region", None),
    )
    return {"bands": list(plans.keys())}


@router.get("/status")
async def radio_status(
    request: Request,
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Report whether a radio (CAT rig) is connected. When connected, optionally include
    current frequency and mode from the rig.
    """
    radio_tx = get_radio_tx_agent(request)
    if not radio_tx:
        return {"connected": False, "reason": "radio_tx_agent_not_available"}
    rig_manager = getattr(radio_tx, "rig_manager", None)
    if not rig_manager or not hasattr(rig_manager, "is_connected"):
        return {"connected": False, "reason": "rig_not_configured"}
    connected = rig_manager.is_connected()
    out: dict[str, Any] = {"connected": connected}
    if connected:
        try:
            state = await rig_manager.get_state()
            if state:
                out["frequency_hz"] = state.frequency
                out["mode"] = getattr(state.mode, "value", str(state.mode))
                out["ptt"] = state.ptt
        except Exception:
            pass
    return out


@router.post("/send-tts")
async def send_tts(
    request: Request,
    body: SendTTSBody,
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Send arbitrary text as TTS over the radio (audio out)."""
    radio_tx = get_radio_tx_agent(request)
    if not radio_tx:
        raise HTTPException(status_code=503, detail="Radio TX agent not available")
    task: dict[str, Any] = {
        "transmission_type": "voice",
        "message": body.message,
        "use_tts": True,
    }
    if body.frequency_hz is not None:
        task["frequency"] = body.frequency_hz
    if body.mode:
        task["mode"] = body.mode
    result = await radio_tx.execute(task)
    if not result.get("success", False):
        detail = result.get("error") or result.get("notes") or "TX failed"
        status = 500
        # Misconfiguration (no rig, SDR TX disabled, etc.) should be surfaced as a service-unavailable error.
        if "Rig manager not configured" in detail or "SDR TX" in detail:
            status = 503
        # HackRF/libusb errors from SDR TX should also be treated as transient service-unavailable conditions.
        if "HackRF libusb error" in detail or "libusb" in detail.lower():
            status = 503
        raise HTTPException(status_code=status, detail=detail)
    return {"ok": True}


@router.post("/send-audio")
async def send_audio(
    request: Request,
    file: UploadFile = File(...),
    frequency_hz: float | None = None,
    mode: str | None = None,
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Transmit an uploaded audio file over radio (CAT or SDR via radio_tx agent).

    This is primarily for live demos where the client cannot reference server-local paths.
    """
    if not file.content_type or not (
        file.content_type.startswith("audio/") or file.content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="Expected audio file")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    radio_tx = get_radio_tx_agent(request)
    if not radio_tx:
        raise HTTPException(status_code=503, detail="Radio TX agent not available")

    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(content)
        temp_path = f.name
    try:
        task: dict[str, Any] = {
            "transmission_type": "voice",
            "message": "",
            "audio_path": temp_path,
            "use_tts": False,
        }
        if frequency_hz is not None:
            task["frequency"] = frequency_hz
        if mode:
            task["mode"] = mode
        result = await radio_tx.execute(task)
        if not result.get("success", False):
            detail = result.get("error") or result.get("notes") or "TX failed"
            status = 500
            if "Rig manager not configured" in detail or "SDR TX" in detail:
                status = 503
            # HackRF/libusb errors from SDR TX should also be treated as transient service-unavailable conditions.
            if "HackRF libusb error" in detail or "libusb" in detail.lower():
                status = 503
            raise HTTPException(status_code=status, detail=detail)
        return {"ok": True, "notes": result.get("notes")}
    finally:
        Path(temp_path).unlink(missing_ok=True)
