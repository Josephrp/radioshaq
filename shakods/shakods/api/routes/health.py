"""Health check endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/ready")
async def ready() -> dict[str, str]:
    """Readiness probe (optional: check DB)."""
    return {"status": "ready"}
