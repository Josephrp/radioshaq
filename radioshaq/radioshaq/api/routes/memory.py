"""Memory REST API: core blocks and daily summaries per callsign."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from radioshaq.api.dependencies import get_current_user
from radioshaq.auth.jwt import TokenPayload

router = APIRouter()

VALID_BLOCK_TYPES = ("user", "identity", "ideaspace")


def _normalize_callsign(callsign: str) -> str:
    return (callsign or "").strip().upper() or "UNKNOWN"


def _callsign_matches_token(callsign: str, user: TokenPayload) -> bool:
    """True if path callsign is allowed for this token (station_id or sub)."""
    norm = _normalize_callsign(callsign)
    sid = (user.station_id or "").strip().upper()
    sub = (user.sub or "").strip().upper()
    return norm == sid or norm == sub


def get_memory_manager(request: Request) -> Any:
    """Return MemoryManager from app state. 503 if not available."""
    manager = getattr(request.app.state, "memory_manager", None)
    if manager is None:
        raise HTTPException(
            status_code=503,
            detail="Memory service not available",
        )
    return manager


@router.get("/{callsign}/blocks")
async def get_blocks(
    callsign: str,
    request: Request,
    user: TokenPayload = Depends(get_current_user),
    memory_manager: Any = Depends(get_memory_manager),
) -> dict[str, Any]:
    """Get core memory blocks (user, identity, ideaspace, system_instructions) for a callsign."""
    if not _callsign_matches_token(callsign, user):
        raise HTTPException(status_code=403, detail="Callsign does not match token")
    try:
        blocks = await memory_manager.get_core_blocks(_normalize_callsign(callsign))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Memory service not available",
        )
    return blocks


@router.put("/{callsign}/blocks/{block_type}")
async def update_block(
    callsign: str,
    block_type: str,
    request: Request,
    body: dict[str, Any],
    user: TokenPayload = Depends(get_current_user),
    memory_manager: Any = Depends(get_memory_manager),
) -> dict[str, Any]:
    """Replace a core block's content."""
    if not _callsign_matches_token(callsign, user):
        raise HTTPException(status_code=403, detail="Callsign does not match token")
    if block_type not in VALID_BLOCK_TYPES:
        raise HTTPException(status_code=400, detail=f"block_type must be one of {VALID_BLOCK_TYPES}")
    content = body.get("content", "")
    try:
        success, message = await memory_manager.update_block(
            _normalize_callsign(callsign), block_type, content
        )
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Memory service not available")
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message}


@router.post("/{callsign}/blocks/{block_type}/append")
async def append_block(
    callsign: str,
    block_type: str,
    request: Request,
    body: dict[str, Any],
    user: TokenPayload = Depends(get_current_user),
    memory_manager: Any = Depends(get_memory_manager),
) -> dict[str, Any]:
    """Append content to a core block."""
    if not _callsign_matches_token(callsign, user):
        raise HTTPException(status_code=403, detail="Callsign does not match token")
    if block_type not in VALID_BLOCK_TYPES:
        raise HTTPException(status_code=400, detail=f"block_type must be one of {VALID_BLOCK_TYPES}")
    content = body.get("content", "")
    try:
        success, message = await memory_manager.append_to_block(
            _normalize_callsign(callsign), block_type, content
        )
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Memory service not available")
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message}


@router.get("/{callsign}/summaries")
async def get_summaries(
    callsign: str,
    request: Request,
    days: int = 7,
    user: TokenPayload = Depends(get_current_user),
    memory_manager: Any = Depends(get_memory_manager),
) -> list[dict[str, Any]]:
    """Get daily summaries for a callsign (last `days` days)."""
    if not _callsign_matches_token(callsign, user):
        raise HTTPException(status_code=403, detail="Callsign does not match token")
    try:
        summaries = await memory_manager.load_daily_summaries(
            _normalize_callsign(callsign), days=days
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Memory service not available",
        )
    return summaries
