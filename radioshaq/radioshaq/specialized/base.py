"""Base class for specialized agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from radioshaq.middleware.upstream import UpstreamEvent


class UpstreamCallback(Protocol):
    """Protocol for upstream event callback."""

    def __call__(self, event: UpstreamEvent) -> Awaitable[None]:
        ...


class SpecializedAgent(ABC):
    """
    Base class for specialized agents that the orchestrator delegates to.

    Subclasses must define name, description, capabilities, and implement execute().
    """

    name: str = ""
    description: str = ""
    capabilities: list[str] = []

    @abstractmethod
    async def execute(
        self,
        task: dict[str, Any],
        upstream_callback: Callable[[UpstreamEvent], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """
        Execute a task and optionally emit upstream events.

        Args:
            task: Task payload (agent-specific keys).
            upstream_callback: Optional callback to emit progress/result/error events.

        Returns:
            Result dict for the orchestrator.
        """
        ...

    async def emit_progress(
        self,
        upstream_callback: Callable[[UpstreamEvent], Awaitable[None]] | None,
        stage: str,
        **payload: Any,
    ) -> None:
        """Emit a progress event if callback is set."""
        if upstream_callback:
            await upstream_callback(
                UpstreamEvent(
                    source=self.name,
                    event_type="progress",
                    payload={"stage": stage, **payload},
                )
            )

    async def emit_result(
        self,
        upstream_callback: Callable[[UpstreamEvent], Awaitable[None]] | None,
        result: dict[str, Any],
    ) -> None:
        """Emit a result event if callback is set."""
        if upstream_callback:
            await upstream_callback(
                UpstreamEvent(
                    source=self.name,
                    event_type="result",
                    payload=result,
                )
            )

    async def emit_error(
        self,
        upstream_callback: Callable[[UpstreamEvent], Awaitable[None]] | None,
        error: str,
        **extra: Any,
    ) -> None:
        """Emit an error event if callback is set."""
        if upstream_callback:
            await upstream_callback(
                UpstreamEvent(
                    source=self.name,
                    event_type="error",
                    payload={"error": error, **extra},
                )
            )
