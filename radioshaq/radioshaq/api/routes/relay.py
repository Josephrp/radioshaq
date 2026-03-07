"""Band-translation (relay) endpoint: receive on one band, store, translate to another band, store."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from radioshaq.api.callsign_whitelist import get_effective_allowed_callsigns, is_callsign_allowed
from radioshaq.api.dependencies import get_config, get_current_user, get_radio_tx_agent, get_transcript_storage
from radioshaq.auth.jwt import TokenPayload
from radioshaq.compliance_plugin import get_band_plan_source_for_config
from radioshaq.radio.injection import get_injection_queue
from radioshaq.relay.service import relay_message_between_bands_service

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
    deliver_at: str | None = Field(None, description="ISO datetime when message should be delivered on target band (optional)")
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
    config = get_config(request)
    radio = config.radio
    band_plans = get_band_plan_source_for_config(
        radio.restricted_bands_region,
        getattr(radio, "band_plan_region", None),
    )
    if source_band not in band_plans or target_band not in band_plans:
        raise HTTPException(status_code=400, detail="Unknown band; use e.g. 40m, 2m, 20m")

    source_plan = band_plans[source_band]
    target_plan = band_plans[target_band]
    source_freq = body.source_frequency_hz or (source_plan.freq_start_hz + (source_plan.freq_end_hz - source_plan.freq_start_hz) / 2)
    target_freq = body.target_frequency_hz or (target_plan.freq_start_hz + (target_plan.freq_end_hz - target_plan.freq_start_hz) / 2)
    source_callsign = (body.source_callsign or "UNKNOWN").upper()
    destination_callsign = (body.destination_callsign or "").upper() or None
    session_id = body.session_id or f"relay-{uuid.uuid4().hex[:12]}"

    allowed = await get_effective_allowed_callsigns(getattr(request.app.state, "db", None), config.radio)
    if not is_callsign_allowed(source_callsign, allowed, config.radio.callsign_registry_required):
        raise HTTPException(status_code=403, detail="Source callsign not allowed")
    if destination_callsign and not is_callsign_allowed(destination_callsign, allowed, config.radio.callsign_registry_required):
        raise HTTPException(status_code=403, detail="Destination callsign not allowed")

    storage = get_transcript_storage(request)
    queue = get_injection_queue()
    radio_tx = get_radio_tx_agent(request)
    result = await relay_message_between_bands_service(
        message=msg,
        source_band=source_band,
        target_band=target_band,
        source_frequency_hz=source_freq,
        target_frequency_hz=target_freq,
        source_callsign=source_callsign,
        destination_callsign=destination_callsign,
        session_id=session_id,
        deliver_at=body.deliver_at,
        storage=storage,
        injection_queue=queue,
        radio_tx_agent=radio_tx,
        config=config.radio,
        source_audio_path=body.source_audio_path,
        target_audio_path=body.target_audio_path,
        store_only_relayed=getattr(config.radio, "relay_store_only_relayed", False),
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Relay failed"))
    if result.get("relay") == "no_storage":
        return result
    return {
        "ok": result["ok"],
        "source_transcript_id": result.get("source_transcript_id"),
        "relayed_transcript_id": result.get("relayed_transcript_id"),
        "source_band": result["source_band"],
        "source_frequency_hz": result["source_frequency_hz"],
        "target_band": result["target_band"],
        "target_frequency_hz": result["target_frequency_hz"],
        "session_id": result["session_id"],
        "deliver_at": result.get("deliver_at"),
    }
