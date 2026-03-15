"""Transcript search endpoint for demo: poll received/relayed messages by band or callsign."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from radioshaq.api.callsign_whitelist import get_effective_allowed_callsigns
from radioshaq.api.dependencies import get_config, get_current_user, get_db, get_radio_tx_agent
from radioshaq.auth.jwt import TokenPayload
from radioshaq.database.transcripts import TranscriptStorage

router = APIRouter()


@router.get("")
async def search_transcripts(
    request: Request,
    callsign: str | None = Query(None, description="Filter by source or destination callsign"),
    frequency_min: float | None = Query(None, description="Minimum frequency (Hz)"),
    frequency_max: float | None = Query(None, description="Maximum frequency (Hz)"),
    mode: str | None = Query(None, description="Filter by mode (FM, PSK31, etc.)"),
    band: str | None = Query(None, description="Filter by band name (e.g. 40m, 2m); uses extra_data.band"),
    destination_only: bool = Query(
        False,
        description="If True and callsign set, return only transcripts where callsign is destination",
    ),
    since: str | None = Query(None, description="Only transcripts after this time (ISO 8601)"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    user: TokenPayload = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    """
    Search transcripts (received/relayed messages). Use for demo so User 2 can poll
    for messages on a band or for their callsign (e.g. after relay from 40m to 2m).
    For a callsign to poll their messages on a band: use callsign=<their_callsign>&destination_only=true&band=<band>.
    Omit band to get messages across all bands.
    When whitelist is configured, only transcripts whose source/destination is in the whitelist are returned.
    """
    if db is None or not hasattr(db, "search_transcripts"):
        return {"transcripts": [], "count": 0}
    storage = TranscriptStorage(db=db)
    results = await storage.search(
        callsign=callsign,
        frequency_min=frequency_min,
        frequency_max=frequency_max,
        mode=mode,
        since=since,
        limit=limit,
        band=band,
        destination_only=destination_only,
    )
    out = list(results)
    config = get_config(request)
    allowed = await get_effective_allowed_callsigns(db, config.radio)
    # When whitelist is applied, include the authenticated user's callsign so they can see their own transcripts
    if allowed:
        user_callsign = (getattr(user, "station_id", None) or getattr(user, "sub", None) or "").strip().upper()
        if user_callsign:
            allowed = set(allowed) | {user_callsign}
        out = [
            t
            for t in out
            if (t.get("source_callsign") in allowed or t.get("destination_callsign") in allowed)
        ]
    return {"transcripts": out, "count": len(out)}


@router.get("/{transcript_id:int}")
async def get_transcript(
    request: Request,
    transcript_id: int,
    user: TokenPayload = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    """Get a single transcript by id (for play or display)."""
    if db is None or not hasattr(db, "get_transcript_by_id"):
        raise HTTPException(status_code=503, detail="Database not available")
    transcript = await db.get_transcript_by_id(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return transcript


@router.post("/{transcript_id:int}/play")
async def play_transcript_over_radio(
    request: Request,
    transcript_id: int,
    user: TokenPayload = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    """Load transcript, generate TTS, and send over radio (audio out)."""
    if db is None or not hasattr(db, "get_transcript_by_id"):
        raise HTTPException(status_code=503, detail="Database not available")
    transcript = await db.get_transcript_by_id(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    radio_tx = get_radio_tx_agent(request)
    if not radio_tx:
        raise HTTPException(status_code=503, detail="Radio TX agent not available")
    text = transcript.get("transcript_text") or ""
    if not text:
        raise HTTPException(status_code=400, detail="Transcript has no text")
    try:
        from radioshaq.audio.tts_plugin import synthesize_speech
    except ImportError:
        raise HTTPException(status_code=503, detail="TTS plugin not available")
    config = get_config(request)
    tts_cfg = getattr(config, "tts", None)
    provider = getattr(tts_cfg, "provider", "elevenlabs") if tts_cfg else "elevenlabs"
    suffix = ".wav" if provider == "kokoro" else ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        temp_path = f.name
    try:
        kwargs: dict[str, Any] = {}
        if tts_cfg and provider == "elevenlabs":
            kwargs["voice"] = getattr(tts_cfg, "elevenlabs_voice_id", None)
            kwargs["model_id"] = getattr(tts_cfg, "elevenlabs_model_id", None)
            kwargs["output_format"] = getattr(tts_cfg, "elevenlabs_output_format", None)
        elif tts_cfg and provider == "kokoro":
            kwargs["voice"] = getattr(tts_cfg, "kokoro_voice", None)
            kwargs["lang_code"] = getattr(tts_cfg, "kokoro_lang_code", None)
            kwargs["speed"] = getattr(tts_cfg, "kokoro_speed", None)
        synthesize_speech(text, provider, output_path=temp_path, **kwargs)
        task = {
            "transmission_type": "voice",
            "message": text,
            "audio_path": temp_path,
            "use_tts": False,
        }
        result = await radio_tx.execute(task)
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "TX failed"))
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail=f"TTS unavailable or synthesis failed: {e}",
        ) from e
    finally:
        Path(temp_path).unlink(missing_ok=True)
    return {"ok": True, "transcript_id": transcript_id}
