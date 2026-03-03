"""HQ mode: central coordination, receives field submissions."""

from __future__ import annotations

from typing import Any

from loguru import logger

from radioshaq.auth.jwt import AuthenticationError, JWTAuthManager, TokenPayload


class HQMode:
    """
    HQ mode: receive authenticated field submissions and coordinate.
    """

    def __init__(
        self,
        orchestrator: Any,
        database: Any = None,
        auth_manager: JWTAuthManager | None = None,
    ):
        self.orchestrator = orchestrator
        self.database = database
        self.auth_manager = auth_manager or JWTAuthManager()
        self._active_operations: dict[str, dict[str, Any]] = {}

    async def receive_field_submission(
        self,
        station_id: str,
        packet: dict[str, Any],
        auth_token: str,
    ) -> dict[str, Any]:
        """Receive and process submission from a field station."""
        payload = self._verify_field_auth(station_id, auth_token)
        if not payload:
            raise AuthenticationError(f"Invalid auth for station {station_id}")

        if self.database and hasattr(self.database, "store_coordination_event"):
            # Store as coordination event if DB supports it
            pass  # Optional: store field submission in DB

        task_id = packet.get("orchestrator_result", {}).get("task_id")
        if self._requires_hq_coordination(packet):
            req = self._build_coordination_request(packet)
            coordination_result = await self.orchestrator.process_request(request=req)
            self._active_operations[task_id or "unknown"] = {
                "station_id": station_id,
                "status": "coordinating",
                "result": coordination_result,
            }
            return {
                "received": True,
                "coordination_active": True,
                "coordination_task_id": coordination_result.state.task_id,
            }
        return {"received": True, "coordination_active": False}

    def _verify_field_auth(self, station_id: str, auth_token: str) -> TokenPayload | None:
        """Verify field station token; return payload or None."""
        try:
            payload = self.auth_manager.verify_token(auth_token)
            if payload.role != "field":
                return None
            if payload.station_id and payload.station_id != station_id:
                return None
            return payload
        except Exception:
            return None

    def _requires_hq_coordination(self, packet: dict[str, Any]) -> bool:
        """True if packet should trigger HQ coordination."""
        return bool(packet.get("orchestrator_result", {}).get("task_id"))

    def _build_coordination_request(self, packet: dict[str, Any]) -> str:
        """Build orchestrator request from field packet."""
        orig = packet.get("original_message", "")
        return f"[Field submission] {orig}"

    async def coordinate_operators(
        self,
        operator_a_callsign: str,
        operator_b_callsign: str,
        purpose: str,
    ) -> dict[str, Any]:
        """Coordinate connection between two operators (scheduling, frequency)."""
        loc_a = None
        loc_b = None
        if self.database:
            if hasattr(self.database, "get_latest_location"):
                loc_a = await self.database.get_latest_location(operator_a_callsign)
                loc_b = await self.database.get_latest_location(operator_b_callsign)
            if hasattr(self.database, "store_coordination_event"):
                await self.database.store_coordination_event(
                    event_type="connect",
                    initiator_callsign=operator_a_callsign,
                    target_callsign=operator_b_callsign,
                    notes=purpose,
                    status="pending",
                )
        coordination_plan = {
            "operator_a": operator_a_callsign,
            "operator_b": operator_b_callsign,
            "purpose": purpose,
            "location_a": loc_a,
            "location_b": loc_b,
            "scheduled_time": None,
            "frequency": None,
            "mode": "FM",
        }
        logger.info("Coordination plan: %s", coordination_plan)
        return {"success": True, "plan": coordination_plan}
