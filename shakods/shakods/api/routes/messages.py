"""Message and orchestrator request endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from shakods.api.dependencies import get_current_user, get_orchestrator
from shakods.auth.jwt import TokenPayload

router = APIRouter()


@router.post("/process")
async def process_message(
    body: dict[str, Any],
    user: TokenPayload = Depends(get_current_user),
    orchestrator: Any = Depends(get_orchestrator),
) -> dict[str, Any]:
    """
    Submit a message for REACT orchestration.
    Requires orchestrator to be set in app state (lifespan).
    """
    if not orchestrator:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not available",
        )
    request_text = body.get("message", body.get("text", ""))
    if not request_text:
        raise HTTPException(status_code=400, detail="message or text required")
    result = await orchestrator.process_request(request=request_text)
    return {
        "success": result.success,
        "message": result.message,
        "task_id": result.state.task_id,
    }
