"""Field mode: edge deployment, propagates to HQ."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Protocol

from loguru import logger


class HQClientProtocol(Protocol):
    """Protocol for HQ client (submit batch, get updates)."""

    async def submit_batch(self, packets: list[dict[str, Any]]) -> bool:
        ...
    async def get_updates(self, station_id: str) -> list[dict[str, Any]]:
        ...


class FieldMode:
    """
    Field mode: run orchestrator locally and propagate results to HQ.
    """

    def __init__(
        self,
        orchestrator: Any,
        hq_client: HQClientProtocol | None = None,
        station_id: str = "FIELD",
        sync_interval_seconds: float = 60.0,
    ):
        self.orchestrator = orchestrator
        self.hq_client = hq_client
        self.station_id = station_id
        self.sync_interval_seconds = sync_interval_seconds
        self._pending_propagation: list[dict[str, Any]] = []

    async def process_message(
        self,
        message: str,
        source: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process message locally and optionally propagate to HQ."""
        result = await self.orchestrator.process_request(request=message)
        propagation_packet = {
            "type": "field_operation",
            "source_station": self.station_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "original_message": message,
            "orchestrator_result": {
                "task_id": result.state.task_id,
                "completed_tasks": [
                    {"task_id": t.task_id, "description": t.description, "status": t.status}
                    for t in result.state.completed_tasks
                ],
                "context": result.state.context,
            },
            "location": None,
        }
        self._pending_propagation.append(propagation_packet)
        await self._propagate_to_hq()
        return {
            "local_result": {
                "success": result.success,
                "message": result.message,
                "task_id": result.state.task_id,
            },
            "propagated": True,
            "propagation_queue_size": len(self._pending_propagation),
        }

    async def _propagate_to_hq(self) -> None:
        """Send pending packets to HQ."""
        if not self._pending_propagation or not self.hq_client:
            return
        try:
            success = await self.hq_client.submit_batch(self._pending_propagation)
            if success:
                self._pending_propagation.clear()
        except Exception as e:
            logger.error("Propagation to HQ failed: {}", e)

    async def run_sync_loop(self) -> None:
        """Background loop: periodic propagate and pull updates."""
        while True:
            await asyncio.sleep(self.sync_interval_seconds)
            if self._pending_propagation:
                await self._propagate_to_hq()
            if self.hq_client:
                try:
                    updates = await self.hq_client.get_updates(station_id=self.station_id)
                    for update in updates:
                        await self._apply_hq_update(update)
                except Exception as e:
                    logger.error("Failed to get updates from HQ: {}", e)

    async def _apply_hq_update(self, update: dict[str, Any]) -> None:
        """Apply an update from HQ (override for custom logic)."""
        logger.debug("HQ update: {}", update)
