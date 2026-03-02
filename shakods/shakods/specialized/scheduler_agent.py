"""Scheduler specialized agent for call scheduling and operator availability."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from shakods.specialized.base import SpecializedAgent


class SchedulerAgent(SpecializedAgent):
    """
    Specialized agent for scheduling contacts and tracking operator availability.
    Uses coordination_events (schedule, relay, etc.) when DB is available.
    """

    name = "scheduler"
    description = "Schedules calls and manages operator availability"
    capabilities = [
        "call_scheduling",
        "operator_availability",
        "list_scheduled_calls",
    ]

    def __init__(self, db: Any = None):
        """Optional: PostGISManager or similar with store_coordination_event, get_pending_coordination_events."""
        self.db = db

    async def execute(
        self,
        task: dict[str, Any],
        upstream_callback: Any = None,
    ) -> dict[str, Any]:
        """Execute scheduler task: schedule_call, list_schedule, get_availability."""
        action = task.get("action", "list_schedule")

        if action == "schedule_call":
            return await self._schedule_call(task, upstream_callback)
        if action == "list_schedule" or action == "get_availability":
            return await self._list_schedule(task, upstream_callback)
        raise ValueError(f"Unknown scheduler action: {action}")

    async def _schedule_call(
        self, task: dict[str, Any], upstream_callback: Any
    ) -> dict[str, Any]:
        """Create a scheduled contact (coordination event)."""
        initiator = task.get("initiator_callsign", "").strip().upper()
        target = (task.get("target_callsign") or "").strip().upper() or None
        scheduled_time = task.get("scheduled_time")  # ISO string or None
        frequency_hz = task.get("frequency_hz")
        mode = task.get("mode", "FM")
        priority = int(task.get("priority", 5))
        notes = task.get("notes")

        if not initiator:
            return {
                "success": False,
                "error": "initiator_callsign is required",
            }

        await self.emit_progress(
            upstream_callback,
            "scheduling",
            initiator_callsign=initiator,
            target_callsign=target,
            scheduled_time=scheduled_time,
        )

        if not self.db:
            return {
                "success": True,
                "initiator_callsign": initiator,
                "target_callsign": target,
                "scheduled_time": scheduled_time,
                "frequency_hz": frequency_hz,
                "mode": mode,
                "notes": "Database not configured; event not persisted",
            }

        try:
            event_id = await self.db.store_coordination_event(
                event_type="schedule",
                initiator_callsign=initiator,
                target_callsign=target,
                scheduled_time=scheduled_time,
                frequency_hz=frequency_hz,
                mode=mode,
                status="pending",
                priority=priority,
                notes=notes,
            )
            await self.emit_result(
                upstream_callback,
                {"event_id": event_id, "status": "pending"},
            )
            return {
                "success": True,
                "event_id": event_id,
                "initiator_callsign": initiator,
                "target_callsign": target,
                "scheduled_time": scheduled_time,
                "frequency_hz": frequency_hz,
                "mode": mode,
                "status": "pending",
            }
        except Exception as e:
            logger.exception("Scheduler store_coordination_event failed: %s", e)
            await self.emit_error(upstream_callback, str(e))
            raise

    async def _list_schedule(
        self, task: dict[str, Any], upstream_callback: Any
    ) -> dict[str, Any]:
        """List scheduled calls / operator availability (pending coordination events)."""
        callsign = task.get("callsign")
        max_results = int(task.get("max_results", 50))

        await self.emit_progress(
            upstream_callback,
            "listing",
            callsign=callsign,
        )

        if not self.db:
            return {
                "success": True,
                "events": [],
                "callsign": callsign,
                "notes": "Database not configured",
            }

        events = await self.db.get_pending_coordination_events(
            callsign=callsign,
            max_results=max_results,
        )
        await self.emit_result(upstream_callback, {"events": events})
        return {
            "success": True,
            "events": events,
            "callsign": callsign,
            "count": len(events),
        }
