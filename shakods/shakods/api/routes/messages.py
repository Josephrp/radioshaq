"""Message and orchestrator request endpoints.

Request body may include InboundMessage-compatible fields for outbound routing:
- message or text: required, content to process
- channel: optional (e.g. whatsapp, sms, api), for future OutboundMessage routing
- chat_id: optional, for future OutboundMessage routing
- sender_id: optional, for logging/context
"""

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
    Optional body fields: channel, chat_id, sender_id (InboundMessage shape for routing).
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
    response: dict[str, Any] = {
        "success": result.success,
        "message": result.message,
        "task_id": result.state.task_id,
    }
    if body.get("channel") is not None:
        response["channel"] = body["channel"]
    if body.get("chat_id") is not None:
        response["chat_id"] = body["chat_id"]
    return response
