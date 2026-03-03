"""Propagation specialized agent (field-to-HQ propagation)."""

from __future__ import annotations

from typing import Any

from radioshaq.specialized.base import SpecializedAgent


class PropagationAgent(SpecializedAgent):
    """
    Specialized agent for field-to-HQ propagation and relay planning.
    Can use GIS agent for distance/band suggestions when db/gis available.
    """

    name = "propagation"
    description = "Field-to-HQ propagation and relay planning"
    capabilities = [
        "propagation_prediction",
        "relay_planning",
    ]

    def __init__(self, gis_agent: Any = None):
        """Optional: GISAgent for location-based propagation."""
        self.gis_agent = gis_agent

    async def execute(
        self,
        task: dict[str, Any],
        upstream_callback: Any = None,
    ) -> dict[str, Any]:
        """Execute propagation task: predict (field-to-HQ) or relay_planning."""
        action = task.get("action", "predict")

        if action == "predict":
            return await self._predict(task, upstream_callback)
        if action == "relay_planning":
            return await self._relay_planning(task, upstream_callback)
        raise ValueError(f"Unknown propagation action: {action}")

    async def _predict(
        self, task: dict[str, Any], upstream_callback: Any
    ) -> dict[str, Any]:
        """Propagation prediction from field (origin) to HQ (destination)."""
        if self.gis_agent:
            # Reuse GIS propagation_prediction
            gis_task = {
                "action": "propagation_prediction",
                "latitude_origin": task.get("field_latitude") or task.get("latitude_origin"),
                "longitude_origin": task.get("field_longitude") or task.get("longitude_origin"),
                "latitude_destination": task.get("hq_latitude") or task.get("latitude_destination"),
                "longitude_destination": task.get("hq_longitude") or task.get("longitude_destination"),
            }
            result = await self.gis_agent.execute(gis_task, upstream_callback)
            result["context"] = "field_to_hq"
            return result

        return {
            "success": True,
            "context": "field_to_hq",
            "notes": "GIS agent not configured; add origin/destination coordinates and GIS for band suggestions.",
        }

    async def _relay_planning(
        self, task: dict[str, Any], upstream_callback: Any
    ) -> dict[str, Any]:
        """Suggest relay operators between field and HQ (uses operators_nearby when GIS available)."""
        if self.gis_agent:
            lat = float(task.get("latitude", 0))
            lon = float(task.get("longitude", 0))
            radius_meters = float(task.get("radius_meters", 100000))
            gis_task = {
                "action": "operators_nearby",
                "latitude": lat,
                "longitude": lon,
                "radius_meters": radius_meters,
                "max_results": 20,
            }
            result = await self.gis_agent.execute(gis_task, upstream_callback)
            result["context"] = "relay_planning"
            result["notes"] = "Candidates for relay; prioritize by distance and band capability."
            return result

        return {
            "success": True,
            "context": "relay_planning",
            "operators": [],
            "notes": "GIS agent not configured for relay planning.",
        }
