"""GIS location and operators-nearby API.

POST/GET /gis/location for operator location CRUD.
GET /gis/operators-nearby for spatial query.
GET /gis/emergency-events for emergency events with locations (for map overlays).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from radioshaq.api.dependencies import get_current_user, get_db
from radioshaq.auth.jwt import TokenPayload
from radioshaq.api.routes.callsigns import CALLSIGN_PATTERN

router = APIRouter()

# Bounds for WGS 84
LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 180.0


class PostLocationBody(BaseModel):
    """Body for POST /gis/location. Provide either (latitude, longitude) or location_text (v1: text alone returns 400)."""

    callsign: str = Field(..., min_length=1, description="Operator callsign")
    latitude: float | None = Field(None, ge=LAT_MIN, le=LAT_MAX, description="Latitude (WGS 84)")
    longitude: float | None = Field(None, ge=LON_MIN, le=LON_MAX, description="Longitude (WGS 84)")
    location_text: str | None = Field(None, description="Free-text place (v1 strict: not used for storage alone)")
    accuracy_meters: float | None = Field(None, ge=0)
    altitude_meters: float | None = Field(None)


class LocationResponse(BaseModel):
    """Response for stored or retrieved location (explicit lat/lon, no raw geometry)."""

    id: int
    callsign: str
    latitude: float
    longitude: float
    source: str
    timestamp: str | None
    confidence: float | None = None


@router.post("/location", response_model=LocationResponse)
async def post_location(
    body: PostLocationBody,
    db: Any = Depends(get_db),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Store operator location. v1 strict: requires latitude and longitude.
    If only location_text is provided, returns 400 with clarification.
    """
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    callsign = body.callsign.strip().upper()
    if not callsign:
        raise HTTPException(status_code=400, detail="callsign is required")
    if not CALLSIGN_PATTERN.match(callsign):
        raise HTTPException(
            status_code=400,
            detail="callsign must be 3–7 alphanumeric chars, optional -digit (e.g. K5ABC or W1XYZ-1)",
        )

    lat, lon = body.latitude, body.longitude
    if lat is not None and lon is not None:
        # Explicit coords: store and return
        loc = await db.store_operator_location(
            callsign=callsign,
            latitude=lat,
            longitude=lon,
            altitude_meters=body.altitude_meters,
            accuracy_meters=body.accuracy_meters,
            source="user_disclosed",
        )
        return {
            "id": loc["id"],
            "callsign": loc["callsign"],
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "source": loc["source"],
            "timestamp": loc["timestamp"],
            "confidence": 1.0,
        }
    # v1 strict: only location_text → 400
    if body.location_text and (lat is None and lon is None):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "ambiguous_location",
                "message": "Provide latitude and longitude for v1. Location text alone is not stored.",
            },
        )
    raise HTTPException(
        status_code=400,
        detail="Provide both latitude and longitude to store location.",
    )


@router.get("/location/{callsign}", response_model=LocationResponse)
async def get_location(
    callsign: str,
    db: Any = Depends(get_db),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Return latest stored location for callsign (explicit lat/lon)."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    normalized = callsign.strip().upper()
    if not normalized:
        raise HTTPException(status_code=400, detail="callsign is required")
    if not CALLSIGN_PATTERN.match(normalized):
        raise HTTPException(
            status_code=400,
            detail="callsign must be 3–7 alphanumeric chars, optional -digit (e.g. K5ABC or W1XYZ-1)",
        )

    loc = await db.get_latest_location_decoded(normalized)
    if loc is None:
        raise HTTPException(status_code=404, detail="No location found for this callsign")

    return {
        "id": loc["id"],
        "callsign": loc["callsign"],
        "latitude": loc["latitude"],
        "longitude": loc["longitude"],
        "source": loc["source"],
        "timestamp": loc["timestamp"],
        "confidence": None,
    }


@router.get("/operators-nearby")
async def get_operators_nearby(
    latitude: float = Query(..., ge=LAT_MIN, le=LAT_MAX),
    longitude: float = Query(..., ge=LON_MIN, le=LON_MAX),
    radius_meters: float = Query(50000, ge=0),
    recent_hours: int = Query(24, ge=0),
    max_results: int = Query(100, ge=1, le=500),
    db: Any = Depends(get_db),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Find operators within radius of a point (from persisted operator_locations)."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    operators = await db.find_operators_nearby(
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        max_results=max_results,
        recent_only=recent_hours > 0,
        recent_hours=recent_hours,
    )
    # Ensure each operator has last_seen_at for mapping clients (alias of timestamp)
    operators_for_response = [
        {**op, "last_seen_at": op.get("last_seen_at") or op.get("timestamp")}
        for op in operators
    ]
    return {
        "latitude": latitude,
        "longitude": longitude,
        "radius_meters": radius_meters,
        "operators": operators_for_response,
        "count": len(operators_for_response),
    }


@router.get("/emergency-events")
async def get_emergency_events_with_locations(
    since: str | None = Query(None, description="ISO timestamp; only events created_at >= since"),
    status: str | None = Query(None, description="Filter by status (e.g. pending, approved)"),
    limit: int = Query(100, ge=1, le=500),
    db: Any = Depends(get_db),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Return emergency coordination events that have a location, with lat/lon for map overlays."""
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")
    if not hasattr(db, "get_emergency_events_with_locations"):
        return {"events": [], "count": 0}
    events = await db.get_emergency_events_with_locations(since=since, status=status, limit=limit)
    return {"events": events, "count": len(events)}
