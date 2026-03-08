"""Registered callsigns (whitelist) API: list, register, register-from-audio, unregister."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from radioshaq.api.dependencies import get_config, get_current_user, get_db
from radioshaq.auth.jwt import TokenPayload
from radioshaq.compliance_plugin import get_band_plan_source_for_config
from radioshaq.config.schema import Config
from radioshaq.constants import EXPLICIT_CONSENT_REGIONS
from radioshaq.radio.bands import BAND_PLANS
from radioshaq.utils.phone import normalize_e164

router = APIRouter()

# Callsign: 3–7 letters/numbers, optional -digit (SSID)
CALLSIGN_PATTERN = re.compile(r"^[A-Z0-9]{3,7}(-[0-9]{1,2})?$", re.IGNORECASE)


class RegisterBody(BaseModel):
    """Body for POST /callsigns/register."""

    callsign: str = Field(..., min_length=3, max_length=10)
    source: str = Field("api", description="api or audio")
    preferred_bands: list[str] | None = Field(None, description="Preferred bands e.g. [40m, 2m]")


class PatchCallsignBandsBody(BaseModel):
    """Body for PATCH /callsigns/registered/{callsign}."""

    preferred_bands: list[str] = Field(..., min_length=0, description="Preferred bands e.g. [40m, 2m]")


# E.164: optional +, digits only (len 10–15)
E164_PATTERN = re.compile(r"^\+?[0-9]{10,15}$")


class PatchContactPreferencesBody(BaseModel):
    """Body for PATCH /callsigns/registered/{callsign}/contact-preferences (§8.1)."""

    notify_sms_phone: str | None = Field(None, description="E.164; set to empty string to clear")
    notify_whatsapp_phone: str | None = Field(None, description="E.164; set to empty string to clear")
    notify_on_relay: bool | None = Field(None, description="Enable notify when a message is left for this callsign")
    consent_source: str | None = Field(None, description="api / web / voice; required when enabling notify_on_relay")
    consent_confirmed: bool | None = Field(
        None,
        description="Explicit consent; required for EU/UK/ZA when enabling notify",
    )




def _normalize_callsign(callsign: str) -> str:
    return callsign.strip().upper()


def _validate_callsign(callsign: str) -> None:
    normalized = _normalize_callsign(callsign)
    if not CALLSIGN_PATTERN.match(normalized):
        raise HTTPException(
            status_code=400,
            detail="Callsign must be 3–7 alphanumeric chars, optional -digit (e.g. K5ABC or W1XYZ-1)",
        )


def _validate_bands(bands: list[str], band_plans: dict | None = None) -> list[str]:
    """Validate band names against band plan. Returns normalized list. Raises HTTPException if invalid."""
    plans = band_plans if band_plans is not None else BAND_PLANS
    out = []
    for b in bands:
        s = (b or "").strip()
        if not s:
            continue
        if s not in plans:
            raise HTTPException(status_code=400, detail=f"Unknown band: {s}. Use e.g. 40m, 2m, 20m")
        out.append(s)
    return out


@router.get("")
async def list_registered(
    request: Request,
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """List all registered callsigns (whitelist)."""
    repo = getattr(request.app.state, "callsign_repository", None)
    if repo is not None:
        registered = await repo.list_registered()
        return {"registered": registered, "count": len(registered)}
    db = getattr(request.app.state, "db", None)
    if db is None or not hasattr(db, "list_registered_callsigns"):
        return {"registered": [], "count": 0}
    registered = await db.list_registered_callsigns()
    return {"registered": registered, "count": len(registered)}


@router.post("/register")
async def register_callsign(
    request: Request,
    body: RegisterBody,
    config: Config = Depends(get_config),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Register a callsign so it is automatically accepted for store/relay."""
    _validate_callsign(body.callsign)
    normalized = _normalize_callsign(body.callsign)
    source = (body.source or "api").strip().lower()
    if source not in ("api", "audio"):
        source = "api"
    radio = config.radio
    band_plans = get_band_plan_source_for_config(
        radio.restricted_bands_region,
        getattr(radio, "band_plan_region", None),
    )
    preferred_bands = None
    if body.preferred_bands:
        preferred_bands = _validate_bands(body.preferred_bands, band_plans)
    repo = getattr(request.app.state, "callsign_repository", None)
    if repo is not None:
        try:
            row_id = await repo.register(normalized, source=source, preferred_bands=preferred_bands)
            return {"ok": True, "callsign": normalized, "id": row_id}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    try:
        row_id = await db.register_callsign(normalized, source=source, preferred_bands=preferred_bands)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "callsign": normalized, "id": row_id}


@router.post("/register-from-audio")
async def register_from_audio(
    request: Request,
    file: UploadFile,
    config: Config = Depends(get_config),
    callsign: str | None = None,
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Upload audio; run ASR and register the extracted or confirmed callsign."""
    if not file.content_type or not (
        file.content_type.startswith("audio/") or file.content_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="Expected audio file")
    # Read to temp file and run ASR
    import tempfile
    from pathlib import Path

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(content)
        temp_path = f.name
    try:
        try:
            from radioshaq.audio.asr_plugin import transcribe_audio
            asr_lang = getattr(config.audio, "asr_language", "en") or "en"
            asr_model = getattr(config.audio, "asr_model", "voxtral") or "voxtral"
            transcript = transcribe_audio(temp_path, model_id=asr_model, language=asr_lang)
        except (ImportError, RuntimeError) as e:
            raise HTTPException(
                status_code=503,
                detail=f"ASR not available: {e!s}",
            )
        transcript = (transcript or "").strip()
        # Use query param if provided; else take first word or try to parse "CALLSIGN de OTHER"
        if callsign:
            normalized = _normalize_callsign(callsign)
            _validate_callsign(callsign)
        else:
            # First token that looks like a callsign
            normalized = None
            for part in transcript.replace(",", " ").split():
                part = part.strip().upper()
                if part and CALLSIGN_PATTERN.match(part):
                    normalized = part
                    break
            else:
                raise HTTPException(
                    status_code=400,
                    detail="No callsign in transcript; provide ?callsign=XXX to confirm",
                )
        repo = getattr(request.app.state, "callsign_repository", None)
        if repo is not None:
            row_id = await repo.register(normalized, source="audio")
            return {"ok": True, "callsign": normalized, "id": row_id, "transcript": transcript[:500]}
        db = getattr(request.app.state, "db", None)
        if db is None:
            raise HTTPException(status_code=503, detail="Database not available")
        row_id = await db.register_callsign(normalized, source="audio")
        return {"ok": True, "callsign": normalized, "id": row_id, "transcript": transcript[:500]}
    finally:
        Path(temp_path).unlink(missing_ok=True)


@router.patch("/registered/{callsign}")
async def patch_callsign_bands(
    request: Request,
    callsign: str,
    body: PatchCallsignBandsBody,
    config: Config = Depends(get_config),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Set preferred_bands for a registered callsign. Band names must be in effective band plan (e.g. 40m, 2m)."""
    normalized = _normalize_callsign(callsign)
    _validate_callsign(callsign)
    radio = config.radio
    band_plans = get_band_plan_source_for_config(
        radio.restricted_bands_region,
        getattr(radio, "band_plan_region", None),
    )
    bands = _validate_bands(body.preferred_bands, band_plans)
    repo = getattr(request.app.state, "callsign_repository", None)
    if repo is not None:
        updated = await repo.update_preferred_bands(normalized, bands)
        if not updated:
            raise HTTPException(status_code=404, detail="Callsign not in registry")
        return {"ok": True, "callsign": normalized, "preferred_bands": bands}
    db = getattr(request.app.state, "db", None)
    if db is None or not hasattr(db, "update_callsign_preferred_bands"):
        raise HTTPException(status_code=503, detail="Database not available")
    updated = await db.update_callsign_preferred_bands(normalized, bands)
    if not updated:
        raise HTTPException(status_code=404, detail="Callsign not in registry")
    return {"ok": True, "callsign": normalized, "preferred_bands": bands}


@router.get("/registered/{callsign}/contact-preferences")
async def get_contact_preferences(
    request: Request,
    callsign: str,
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Get contact preferences for a registered callsign (§8.1)."""
    normalized = _normalize_callsign(callsign)
    _validate_callsign(callsign)
    db = getattr(request.app.state, "db", None)
    if db is None or not hasattr(db, "get_contact_preferences"):
        raise HTTPException(status_code=503, detail="Database not available")
    prefs = await db.get_contact_preferences(normalized)
    if prefs is None:
        raise HTTPException(status_code=404, detail="Callsign not in registry")
    return prefs


def _require_explicit_consent_region(region: str) -> bool:
    """True if region requires explicit consent (EU/UK/ZA)."""
    return (region or "").strip().upper() in EXPLICIT_CONSENT_REGIONS


@router.patch("/registered/{callsign}/contact-preferences")
async def patch_contact_preferences(
    request: Request,
    callsign: str,
    body: PatchContactPreferencesBody,
    config: Config = Depends(get_config),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Set contact preferences (notify by SMS/WhatsApp when a message is left for this callsign). Sets consent_at when enabling notify_on_relay (§8.1)."""
    normalized = _normalize_callsign(callsign)
    _validate_callsign(callsign)
    region = getattr(config.radio, "restricted_bands_region", None) or ""
    if body.notify_on_relay is True:
        if not body.consent_source or body.consent_source.strip() not in ("api", "web", "voice"):
            raise HTTPException(
                status_code=400,
                detail="consent_source (api / web / voice) required when enabling notify_on_relay",
            )
        if _require_explicit_consent_region(region) and body.consent_confirmed is not True:
            raise HTTPException(
                status_code=400,
                detail="consent_confirmed=true required for this region when enabling notify",
            )
    sms_phone = None
    if body.notify_sms_phone is not None:
        raw = (body.notify_sms_phone or "").strip()
        if raw:
            sms_phone = normalize_e164(raw)
            if not E164_PATTERN.match(sms_phone):
                raise HTTPException(status_code=400, detail="notify_sms_phone must be E.164 (10–15 digits)")
        else:
            sms_phone = ""
    whatsapp_phone = None
    if body.notify_whatsapp_phone is not None:
        raw = (body.notify_whatsapp_phone or "").strip()
        if raw:
            whatsapp_phone = normalize_e164(raw)
            if not E164_PATTERN.match(whatsapp_phone):
                raise HTTPException(status_code=400, detail="notify_whatsapp_phone must be E.164 (10–15 digits)")
        else:
            whatsapp_phone = ""
    db = getattr(request.app.state, "db", None)
    if db is None or not hasattr(db, "set_contact_preferences"):
        raise HTTPException(status_code=503, detail="Database not available")
    from datetime import datetime, timezone
    consent_at = datetime.now(timezone.utc) if (body.notify_on_relay is True and body.consent_source) else None
    consent_source = (body.consent_source or "").strip() or None
    if consent_at and not consent_source:
        consent_source = "api"
    updated = await db.set_contact_preferences(
        normalized,
        notify_sms_phone=sms_phone if sms_phone is not None else None,
        notify_whatsapp_phone=whatsapp_phone if whatsapp_phone is not None else None,
        notify_on_relay=body.notify_on_relay,
        consent_at=consent_at,
        consent_source=consent_source,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Callsign not in registry")
    prefs = await db.get_contact_preferences(normalized)
    return prefs or {}


@router.delete("/registered/{callsign}")
async def unregister_callsign(
    request: Request,
    callsign: str,
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Remove a callsign from the registry."""
    normalized = _normalize_callsign(callsign)
    repo = getattr(request.app.state, "callsign_repository", None)
    if repo is not None:
        removed = await repo.unregister(normalized)
        if not removed:
            raise HTTPException(status_code=404, detail="Callsign not in registry")
        return {"ok": True}
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    removed = await db.unregister_callsign(normalized)
    if not removed:
        raise HTTPException(status_code=404, detail="Callsign not in registry")
    return {"ok": True}
