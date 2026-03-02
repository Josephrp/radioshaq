"""Memory and result upstreaming middleware for specialized agents."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Awaitable

from loguru import logger

from shakods.orchestrator.react_loop import REACTState


@dataclass
class UpstreamEvent:
    """Event to be upstreamed to orchestrator."""

    source: str
    event_type: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 5


class MemoryUpstreamMiddleware:
    """
    Middleware for upstreaming memories and results from specialized agents
    back to the orchestrator's context.
    """

    def __init__(self, max_queue_size: int = 1000) -> None:
        self._event_queue: asyncio.Queue[UpstreamEvent] = asyncio.Queue(
            maxsize=max_queue_size
        )
        self._subscribed_sources: set[str] = set()
        self._handlers: list[Callable[[UpstreamEvent], Awaitable[None]]] = []

    def emit(self, event: UpstreamEvent) -> None:
        """Emit an upstream event (non-blocking)."""
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(
                "Upstream event queue full, dropping event from %s", event.source
            )

    def subscribe(self, source_id: str) -> None:
        """Mark a source as subscribed (for filtering/logging)."""
        self._subscribed_sources.add(source_id)

    def add_handler(
        self, handler: Callable[[UpstreamEvent], Awaitable[None]]
    ) -> None:
        """Add a handler for upstream events."""
        self._handlers.append(handler)

    async def process_upstream_events(self, context: REACTState) -> None:
        """Process queued upstream events and update orchestrator context."""
        processed = 0
        while not self._event_queue.empty():
            try:
                event = self._event_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            if event.event_type == "memory":
                await self._integrate_memory(event, context)
            elif event.event_type == "result":
                await self._integrate_result(event, context)
            elif event.event_type == "progress":
                await self._update_progress(event, context)
            elif event.event_type == "error":
                await self._handle_error(event, context)

            for handler in self._handlers:
                try:
                    await handler(event)
                except Exception as e:
                    logger.warning("Upstream handler error: %s", e)

            processed += 1

        if processed:
            logger.debug("Processed %d upstream events into context", processed)

    async def _integrate_memory(self, event: UpstreamEvent, context: REACTState) -> None:
        """Integrate upstreamed memory into orchestrator context."""
        memory = event.payload.get("memory")
        if memory:
            context.context.setdefault("upstream_memories", []).append(
                {"source": event.source, "memory": memory, "timestamp": str(event.timestamp)}
            )

    async def _integrate_result(
        self, event: UpstreamEvent, context: REACTState
    ) -> None:
        """Integrate upstreamed result into orchestrator context."""
        result = event.payload
        context.context.setdefault("upstream_results", []).append(
            {"source": event.source, "result": result, "timestamp": str(event.timestamp)}
        )

    async def _update_progress(
        self, event: UpstreamEvent, context: REACTState
    ) -> None:
        """Update progress in orchestrator context."""
        context.context.setdefault("upstream_progress", []).append(
            {
                "source": event.source,
                "stage": event.payload.get("stage", "unknown"),
                "payload": event.payload,
                "timestamp": str(event.timestamp),
            }
        )

    async def _handle_error(self, event: UpstreamEvent, context: REACTState) -> None:
        """Handle error event - add to context for orchestrator awareness."""
        context.context.setdefault("upstream_errors", []).append(
            {
                "source": event.source,
                "error": event.payload.get("error", event.payload),
                "timestamp": str(event.timestamp),
            }
        )
