"""Radio and propagation endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from radioshaq.api.dependencies import get_current_user, get_radio_tx_agent
from radioshaq.auth.jwt import TokenPayload
from radioshaq.database.gis import propagation_prediction

router = APIRouter()


class SendTTSBody(BaseModel):
    """Body for POST /radio/send-tts."""

    message: str = Field(..., min_length=1)
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
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, list[str]]:
    """List supported bands (from band plan)."""
    from radioshaq.radio.bands import BAND_PLANS
    return {"bands": list(BAND_PLANS.keys())}


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
        raise HTTPException(status_code=500, detail=result.get("error", "TX failed"))
    return {"ok": True}
