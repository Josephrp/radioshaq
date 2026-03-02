"""Transcript search endpoint for demo: poll received/relayed messages by band or callsign."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from shakods.api.dependencies import get_current_user, get_db
from shakods.auth.jwt import TokenPayload
from shakods.database.transcripts import TranscriptStorage

router = APIRouter()


@router.get("")
async def search_transcripts(
    callsign: str | None = Query(None, description="Filter by source or destination callsign"),
    frequency_min: float | None = Query(None, description="Minimum frequency (Hz)"),
    frequency_max: float | None = Query(None, description="Maximum frequency (Hz)"),
    mode: str | None = Query(None, description="Filter by mode (FM, PSK31, etc.)"),
    band: str | None = Query(None, description="Filter by band name (e.g. 40m, 2m); uses extra_data.band"),
    since: str | None = Query(None, description="Only transcripts after this time (ISO 8601)"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    user: TokenPayload = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> dict[str, Any]:
    """
    Search transcripts (received/relayed messages). Use for demo so User 2 can poll
    for messages on a band or for their callsign (e.g. after relay from 40m to 2m).
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
    )
    out = list(results)
    if band:
        out = [t for t in out if (t.get("extra_data") or {}).get("band") == band]
    return {"transcripts": out, "count": len(out)}
