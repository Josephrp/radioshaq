"""Registered callsigns (whitelist) API: list, register, register-from-audio, unregister."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from radioshaq.api.dependencies import get_config, get_current_user, get_db
from radioshaq.auth.jwt import TokenPayload
from radioshaq.config.schema import Config
from radioshaq.radio.bands import BAND_PLANS

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


def _normalize_callsign(callsign: str) -> str:
    return callsign.strip().upper()


def _validate_callsign(callsign: str) -> None:
    normalized = _normalize_callsign(callsign)
    if not CALLSIGN_PATTERN.match(normalized):
        raise HTTPException(
            status_code=400,
            detail="Callsign must be 3–7 alphanumeric chars, optional -digit (e.g. K5ABC or W1XYZ-1)",
        )


def _validate_bands(bands: list[str]) -> list[str]:
    """Validate band names against BAND_PLANS. Returns normalized list. Raises HTTPException if invalid."""
    out = []
    for b in bands:
        s = (b or "").strip()
        if not s:
            continue
        if s not in BAND_PLANS:
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
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Register a callsign so it is automatically accepted for store/relay."""
    _validate_callsign(body.callsign)
    normalized = _normalize_callsign(body.callsign)
    source = (body.source or "api").strip().lower()
    if source not in ("api", "audio"):
        source = "api"
    preferred_bands = None
    if body.preferred_bands:
        preferred_bands = _validate_bands(body.preferred_bands)
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
            from radioshaq.audio.asr import transcribe_audio_voxtral
            asr_lang = getattr(config.audio, "asr_language", "en") or "en"
            transcript = transcribe_audio_voxtral(temp_path, language=asr_lang)
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="ASR not available (install with uv sync --extra audio)",
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


@router.patch("/registered/{callsign:path}")
async def patch_callsign_bands(
    request: Request,
    callsign: str,
    body: PatchCallsignBandsBody,
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Set preferred_bands for a registered callsign. Band names must be in BAND_PLANS (e.g. 40m, 2m)."""
    normalized = _normalize_callsign(callsign)
    _validate_callsign(callsign)
    bands = _validate_bands(body.preferred_bands)
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


@router.delete("/registered/{callsign:path}")
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
