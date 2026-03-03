"""Health check endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, Any]:
    """Readiness probe: DB (if configured), orchestrator, optional audio agent."""
    out: dict[str, Any] = {"status": "ready", "checks": {}}
    if getattr(request.app.state, "db", None) is not None:
        out["checks"]["database"] = "connected"
    if getattr(request.app.state, "orchestrator", None) is not None:
        out["checks"]["orchestrator"] = "available"
    registry = getattr(request.app.state, "agent_registry", None)
    if registry:
        audio_agent = registry.get_agent("radio_rx_audio") if hasattr(registry, "get_agent") else None
        out["checks"]["audio_agent"] = "registered" if audio_agent else "not_registered"
    return out
