"""Radio and propagation endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Query

from shakods.api.dependencies import get_current_user
from shakods.auth.jwt import TokenPayload
from shakods.database.gis import propagation_prediction

router = APIRouter()


@router.get("/propagation")
async def propagation(
    lat_origin: float = Query(..., description="Origin latitude"),
    lon_origin: float = Query(..., description="Origin longitude"),
    lat_dest: float = Query(..., description="Destination latitude"),
    lon_dest: float = Query(..., description="Destination longitude"),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Get propagation prediction between two points."""
    return propagation_prediction(lat_origin, lon_origin, lat_dest, lon_dest)


@router.get("/bands")
async def bands(
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, list[str]]:
    """List supported bands (from band plan)."""
    from shakods.radio.bands import BAND_PLANS
    return {"bands": list(BAND_PLANS.keys())}
