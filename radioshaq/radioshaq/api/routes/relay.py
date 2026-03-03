"""Band-translation (relay) endpoint: receive on one band, store, translate to another band, store."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from radioshaq.api.callsign_whitelist import get_effective_allowed_callsigns, is_callsign_allowed
from radioshaq.api.dependencies import get_config, get_current_user, get_transcript_storage
from radioshaq.auth.jwt import TokenPayload
from radioshaq.radio.bands import BAND_PLANS

router = APIRouter()


class RelayBody(BaseModel):
    """Body for POST /messages/relay (band translation)."""

    message: str = Field(..., min_length=1)
    source_band: str = Field(...)
    target_band: str = Field(...)
    source_frequency_hz: float | None = Field(None)
    target_frequency_hz: float | None = Field(None)
    source_callsign: str = Field("UNKNOWN")
    destination_callsign: str | None = Field(None)
    session_id: str | None = Field(None)
    source_audio_path: str | None = Field(None)
    target_audio_path: str | None = Field(None)


@router.post("/relay")
async def relay_message_between_bands(
    request: Request,
    body: RelayBody,
    user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Translate a message from one band to another and store both sides.

    Scenario: User A emits on band A (e.g. 40m), message is received and stored;
    then it is "relayed" to band B (e.g. 2m) for User B. Stores:
    1. Original (or reference) transcript on source band
    2. Relay transcript on target band with metadata linking to source

    Body:
    - message (str): Text to relay
    - source_band (str): e.g. "40m"
    - source_frequency_hz (float, optional): exact freq if known
    - source_callsign (str): who sent on source band
    - target_band (str): e.g. "2m"
    - target_frequency_hz (float, optional): target freq; else use band default
    - destination_callsign (str, optional): who receives on target band
    - session_id (str, optional): default generated
    """
    msg = body.message
    source_band = body.source_band
    target_band = body.target_band
    if source_band not in BAND_PLANS or target_band not in BAND_PLANS:
        raise HTTPException(status_code=400, detail="Unknown band; use e.g. 40m, 2m, 20m")

    source_plan = BAND_PLANS[source_band]
    target_plan = BAND_PLANS[target_band]
    source_freq = body.source_frequency_hz or (source_plan.freq_start_hz + (source_plan.freq_end_hz - source_plan.freq_start_hz) / 2)
    target_freq = body.target_frequency_hz or (target_plan.freq_start_hz + (target_plan.freq_end_hz - target_plan.freq_start_hz) / 2)
    source_callsign = (body.source_callsign or "UNKNOWN").upper()
    destination_callsign = (body.destination_callsign or "").upper() or None
    session_id = body.session_id or f"relay-{uuid.uuid4().hex[:12]}"

    config = get_config(request)
    allowed = await get_effective_allowed_callsigns(getattr(request.app.state, "db", None), config.radio)
    if not is_callsign_allowed(source_callsign, allowed, config.radio.callsign_registry_required):
        raise HTTPException(status_code=403, detail="Source callsign not allowed")
    if destination_callsign and not is_callsign_allowed(destination_callsign, allowed, config.radio.callsign_registry_required):
        raise HTTPException(status_code=403, detail="Destination callsign not allowed")

    storage = get_transcript_storage(request)
    if not storage or not getattr(storage, "_db", None):
        # No DB: return relay plan without persisting
        return {
            "ok": True,
            "relay": "no_storage",
            "message": "Relay accepted (no DB to store)",
            "source_band": source_band,
            "source_frequency_hz": source_freq,
            "target_band": target_band,
            "target_frequency_hz": target_freq,
            "source_callsign": source_callsign,
            "destination_callsign": destination_callsign,
        }
    mode = (source_plan.modes or ["SSB"])[0]
    target_mode = (target_plan.modes or ["FM"])[0]

    # 1) Store original (received on source band)
    source_metadata = {"band": source_band, "relay_role": "source"}
    orig_id = await storage.store(
        session_id=session_id,
        source_callsign=source_callsign,
        frequency_hz=source_freq,
        mode=mode,
        transcript_text=msg,
        destination_callsign=destination_callsign,
        metadata=source_metadata,
        raw_audio_path=body.source_audio_path,
    )

    # 2) Store relayed (translated to target band)
    relay_metadata = {
        "band": target_band,
        "relay_role": "relayed",
        "relay_from_transcript_id": orig_id,
        "relay_from_band": source_band,
        "relay_from_frequency_hz": source_freq,
    }
    relay_id = await storage.store(
        session_id=session_id,
        source_callsign=source_callsign,
        frequency_hz=target_freq,
        mode=target_mode,
        transcript_text=msg,
        destination_callsign=destination_callsign,
        metadata=relay_metadata,
        raw_audio_path=body.target_audio_path,
    )

    return {
        "ok": True,
        "source_transcript_id": orig_id,
        "relayed_transcript_id": relay_id,
        "source_band": source_band,
        "source_frequency_hz": source_freq,
        "target_band": target_band,
        "target_frequency_hz": target_freq,
        "session_id": session_id,
    }
