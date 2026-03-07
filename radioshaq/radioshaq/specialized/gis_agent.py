"""GIS specialized agent for location analysis and propagation prediction."""

from __future__ import annotations

import math
from typing import Any

from loguru import logger

from radioshaq.specialized.base import SpecializedAgent


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate distance in km between two WGS84 points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class GISAgent(SpecializedAgent):
    """
    Specialized agent for geographic information and propagation.
    Uses PostGIS for operator locations; simple distance-based propagation when no external service.
    """

    name = "gis"
    description = "Location analysis and propagation prediction for ham radio"
    capabilities = [
        "operators_nearby",
        "operator_location",
        "set_operator_location",
        "propagation_prediction",
    ]

    def __init__(self, db: Any = None):
        """Optional: PostGISManager with find_operators_nearby, get_latest_location."""
        self.db = db

    async def execute(
        self,
        task: dict[str, Any],
        upstream_callback: Any = None,
    ) -> dict[str, Any]:
        """Execute GIS task: operators_nearby, get_location, set_location, propagation_prediction."""
        action = task.get("action", "operators_nearby")

        if action == "operators_nearby":
            return await self._operators_nearby(task, upstream_callback)
        if action == "get_location":
            return await self._get_location(task, upstream_callback)
        if action == "set_location":
            return await self._set_location(task, upstream_callback)
        if action == "propagation_prediction":
            return await self._propagation_prediction(task, upstream_callback)
        raise ValueError(f"Unknown GIS action: {action}")

    async def _operators_nearby(
        self, task: dict[str, Any], upstream_callback: Any
    ) -> dict[str, Any]:
        """Find operators within radius of a point. Falls back to stored location when center coords omitted."""
        lat_raw = task.get("latitude")
        lon_raw = task.get("longitude")
        center_provided = lat_raw is not None and lon_raw is not None
        if not center_provided and self.db:
            callsign = (task.get("callsign") or "").strip().upper()
            if callsign:
                stored = await self.db.get_latest_location_decoded(callsign)
                if stored:
                    lat_raw = lat_raw if lat_raw is not None else stored["latitude"]
                    lon_raw = lon_raw if lon_raw is not None else stored["longitude"]
        lat = float(lat_raw) if lat_raw is not None else 0.0
        lon = float(lon_raw) if lon_raw is not None else 0.0
        radius_meters = float(task.get("radius_meters", 50000))
        max_results = int(task.get("max_results", 50))
        recent_hours = int(task.get("recent_hours", 24))

        await self.emit_progress(
            upstream_callback,
            "querying",
            latitude=lat,
            longitude=lon,
            radius_meters=radius_meters,
        )

        if not self.db:
            return {
                "success": True,
                "operators": [],
                "latitude": lat,
                "longitude": lon,
                "radius_meters": radius_meters,
                "notes": "Database not configured",
            }

        try:
            operators = await self.db.find_operators_nearby(
                latitude=lat,
                longitude=lon,
                radius_meters=radius_meters,
                max_results=max_results,
                recent_only=True,
                recent_hours=recent_hours,
            )
            await self.emit_result(upstream_callback, {"operators": operators})
            return {
                "success": True,
                "operators": operators,
                "latitude": lat,
                "longitude": lon,
                "radius_meters": radius_meters,
                "count": len(operators),
            }
        except Exception as e:
            logger.exception("GIS find_operators_nearby failed: %s", e)
            await self.emit_error(upstream_callback, str(e))
            raise

    async def _get_location(
        self, task: dict[str, Any], upstream_callback: Any
    ) -> dict[str, Any]:
        """Get latest location for a callsign (decoded lat/lon, JSON-serializable)."""
        callsign = (task.get("callsign") or "").strip().upper()
        if not callsign:
            return {"success": False, "error": "callsign is required"}

        await self.emit_progress(upstream_callback, "querying", callsign=callsign)

        if not self.db:
            return {
                "success": True,
                "callsign": callsign,
                "location": None,
                "notes": "Database not configured",
            }

        try:
            location = await self.db.get_latest_location_decoded(callsign)
            await self.emit_result(upstream_callback, {"location": location})
            return {
                "success": True,
                "callsign": callsign,
                "location": location,
            }
        except Exception as e:
            logger.exception("GIS get_latest_location failed: %s", e)
            await self.emit_error(upstream_callback, str(e))
            raise

    async def _set_location(
        self, task: dict[str, Any], upstream_callback: Any
    ) -> dict[str, Any]:
        """Store operator location (source=user_disclosed) for reuse in propagation/nearby."""
        callsign = (task.get("callsign") or "").strip().upper()
        if not callsign:
            return {"success": False, "error": "callsign is required"}
        try:
            lat = float(task.get("latitude"))
            lon = float(task.get("longitude"))
        except (TypeError, ValueError):
            return {"success": False, "error": "latitude and longitude are required (numeric)"}

        await self.emit_progress(upstream_callback, "storing", callsign=callsign, latitude=lat, longitude=lon)

        if not self.db:
            return {"success": False, "error": "Database not configured"}

        try:
            loc = await self.db.store_operator_location(
                callsign=callsign,
                latitude=lat,
                longitude=lon,
                altitude_meters=task.get("altitude_meters"),
                accuracy_meters=task.get("accuracy_meters"),
                source="user_disclosed",
            )
            await self.emit_result(upstream_callback, {"location": loc})
            return {
                "success": True,
                "id": loc["id"],
                "callsign": loc["callsign"],
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "source": loc["source"],
                "timestamp": loc["timestamp"],
            }
        except Exception as e:
            logger.exception("GIS set_location failed: %s", e)
            await self.emit_error(upstream_callback, str(e))
            raise

    async def _propagation_prediction(
        self, task: dict[str, Any], upstream_callback: Any
    ) -> dict[str, Any]:
        """Simple propagation: distance between two points and band suggestion. Uses stored location as origin only when origin not provided."""
        # Use explicit sentinel: only fall back when origin keys are missing (not when 0.0, which is valid)
        lat1_raw = task.get("latitude_origin")
        lon1_raw = task.get("longitude_origin")
        origin_provided = lat1_raw is not None and lon1_raw is not None
        lat1 = float(lat1_raw) if lat1_raw is not None else 0.0
        lon1 = float(lon1_raw) if lon1_raw is not None else 0.0
        lat2 = float(task.get("latitude_destination", 0))
        lon2 = float(task.get("longitude_destination", 0))

        # Fallback: use stored operator location as origin only when caller did not provide origin coords
        if not origin_provided and self.db:
            callsign = (task.get("callsign") or "").strip().upper()
            if callsign:
                stored = await self.db.get_latest_location_decoded(callsign)
                if stored:
                    lat1 = stored["latitude"]
                    lon1 = stored["longitude"]

        await self.emit_progress(
            upstream_callback,
            "computing",
            latitude_origin=lat1,
            longitude_origin=lon1,
        )

        distance_km = _haversine_km(lat1, lon1, lat2, lon2)
        # Rough band guidance: <50km 2m/70cm, <500km HF/6m, <3000km HF, >3000km HF long path
        if distance_km < 50:
            suggested_bands = ["2m", "70cm"]
            notes = "Short range; VHF/UHF suitable."
        elif distance_km < 500:
            suggested_bands = ["6m", "2m", "10m", "20m"]
            notes = "Medium range; 6m/10m/20m may work."
        elif distance_km < 3000:
            suggested_bands = ["20m", "40m", "15m"]
            notes = "Long range; HF recommended."
        else:
            suggested_bands = ["20m", "40m", "15m", "10m"]
            notes = "Very long range; HF with possible long path."

        result = {
            "success": True,
            "distance_km": round(distance_km, 2),
            "origin": {"latitude": lat1, "longitude": lon1},
            "destination": {"latitude": lat2, "longitude": lon2},
            "suggested_bands": suggested_bands,
            "notes": notes,
        }
        await self.emit_result(upstream_callback, result)
        return result
