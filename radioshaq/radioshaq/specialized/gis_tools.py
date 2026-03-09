"""GIS tools for orchestrator (LLM-callable): set/get operator location, operators nearby."""

from __future__ import annotations

import json
from typing import Any

LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 180.0


class SetOperatorLocationTool:
    """Store the operator's current location (latitude, longitude) for later use in propagation and nearby queries."""

    name = "set_operator_location"
    description = "Store the operator's current location (latitude, longitude) for later use in propagation and nearby queries."

    def __init__(self, db: Any = None) -> None:
        self.db = db

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "callsign": {"type": "string", "description": "Operator callsign"},
                        "latitude": {"type": "number", "description": "Latitude (WGS 84)"},
                        "longitude": {"type": "number", "description": "Longitude (WGS 84)"},
                        "altitude_meters": {"type": "number", "description": "Optional altitude in meters"},
                        "accuracy_meters": {"type": "number", "description": "Optional accuracy estimate in meters"},
                    },
                    "required": ["callsign", "latitude", "longitude"],
                },
            },
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors = []
        if not (params.get("callsign") or "").strip():
            errors.append("callsign is required")
        lat = params.get("latitude")
        lon = params.get("longitude")
        if lat is None:
            errors.append("latitude is required")
        elif not isinstance(lat, (int, float)) or lat < LAT_MIN or lat > LAT_MAX:
            errors.append("latitude must be between -90 and 90")
        if lon is None:
            errors.append("longitude is required")
        elif not isinstance(lon, (int, float)) or lon < LON_MIN or lon > LON_MAX:
            errors.append("longitude must be between -180 and 180")
        return errors

    async def execute(
        self,
        callsign: str,
        latitude: float,
        longitude: float,
        altitude_meters: float | None = None,
        accuracy_meters: float | None = None,
        **kwargs: Any,
    ) -> str:
        if self.db is None:
            return json.dumps({"error": "Database not available"})
        cs = str(callsign).strip().upper()
        if not cs:
            return json.dumps({"error": "callsign is required"})
        try:
            loc = await self.db.store_operator_location(
                callsign=cs,
                latitude=float(latitude),
                longitude=float(longitude),
                altitude_meters=altitude_meters,
                accuracy_meters=accuracy_meters,
                source="user_disclosed",
            )
            return json.dumps({
                "id": loc["id"],
                "callsign": loc["callsign"],
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "source": loc["source"],
                "timestamp": loc["timestamp"],
            })
        except Exception as e:
            return json.dumps({"error": str(e)})


class GetOperatorLocationTool:
    """Get the latest stored location for a callsign."""

    name = "get_operator_location"
    description = "Get the latest stored location for a callsign (latitude, longitude, source, timestamp)."

    def __init__(self, db: Any = None) -> None:
        self.db = db

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "callsign": {"type": "string", "description": "Operator callsign"},
                    },
                    "required": ["callsign"],
                },
            },
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        if not (params.get("callsign") or "").strip():
            return ["callsign is required"]
        return []

    async def execute(self, callsign: str, **kwargs: Any) -> str:
        if self.db is None:
            return json.dumps({"error": "Database not available"})
        cs = str(callsign).strip().upper()
        if not cs:
            return json.dumps({"error": "callsign is required"})
        loc = await self.db.get_latest_location_decoded(cs)
        if loc is None:
            return json.dumps({"callsign": cs, "location": None, "message": "No location stored for this callsign"})
        return json.dumps({
            "callsign": loc["callsign"],
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "source": loc["source"],
            "timestamp": loc["timestamp"],
        })


class OperatorsNearbyTool:
    """Find operators within a radius of a point (latitude, longitude)."""

    name = "operators_nearby"
    description = "Find operators within a radius of a point (latitude, longitude). Returns list with distance_meters."

    def __init__(self, db: Any = None) -> None:
        self.db = db

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "latitude": {"type": "number", "description": "Center latitude"},
                        "longitude": {"type": "number", "description": "Center longitude"},
                        "radius_meters": {"type": "number", "description": "Search radius in meters", "default": 50000},
                        "recent_hours": {"type": "integer", "description": "Only include locations from last N hours", "default": 24},
                        "max_results": {"type": "integer", "description": "Maximum number of results", "default": 50},
                    },
                    "required": ["latitude", "longitude"],
                },
            },
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors = []
        lat = params.get("latitude")
        lon = params.get("longitude")
        if lat is None:
            errors.append("latitude is required")
        elif not isinstance(lat, (int, float)) or lat < LAT_MIN or lat > LAT_MAX:
            errors.append("latitude must be between -90 and 90")
        if lon is None:
            errors.append("longitude is required")
        elif not isinstance(lon, (int, float)) or lon < LON_MIN or lon > LON_MAX:
            errors.append("longitude must be between -180 and 180")
        return errors

    async def execute(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float = 50000,
        recent_hours: int = 24,
        max_results: int = 50,
        **kwargs: Any,
    ) -> str:
        if self.db is None:
            return json.dumps({"operators": [], "notes": "Database not available"})
        try:
            operators = await self.db.find_operators_nearby(
                latitude=float(latitude),
                longitude=float(longitude),
                radius_meters=float(radius_meters),
                max_results=int(max_results),
                recent_only=int(recent_hours) > 0,
                recent_hours=int(recent_hours),
            )
            return json.dumps({
                "latitude": latitude,
                "longitude": longitude,
                "radius_meters": radius_meters,
                "operators": operators,
                "count": len(operators),
            })
        except Exception as e:
            return json.dumps({"error": str(e), "operators": []})
