"""Middleware system for RadioShaq (adapted from vibe).

Provides a middleware pipeline for processing conversations through
the REACT loop with support for context management, limits, and
custom middleware.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from datetime import datetime


class MiddlewareAction(StrEnum):
    """Actions that middleware can request from the orchestrator."""
    
    CONTINUE = auto()
    """Continue normal processing."""
    
    STOP = auto()
    """Stop the current conversation/task."""
    
    COMPACT = auto()
    """Compact/trim the context to reduce tokens."""
    
    INJECT_MESSAGE = auto()
    """Inject a message into the conversation."""
    
    UPSTREAM = auto()
    """Upstream results/memories to parent orchestrator."""
    
    DELEGATE = auto()
    """Delegate to a specialized agent."""


class ResetReason(StrEnum):
    """Reasons for resetting middleware state."""
    
    STOP = auto()
    COMPACT = auto()
    PHASE_CHANGE = auto()
    ERROR = auto()


@dataclass
class AgentStats:
    """Statistics for an agent/orchestrator session."""
    
    steps: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    tool_calls: int = 0
    tool_errors: int = 0
    upstream_events: int = 0
    session_cost: float = 0.0
    start_time: datetime | None = None
    
    def reset(self) -> None:
        """Reset all statistics."""
        self.steps = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.tool_calls = 0
        self.tool_errors = 0
        self.upstream_events = 0
        self.session_cost = 0.0


@dataclass
class ConversationContext:
    """Context passed through middleware pipeline.
    
    This contains the current state of a conversation/task
    being processed by the REACT orchestrator.
    """
    
    messages: list[dict[str, Any]]
    stats: AgentStats
    metadata: dict[str, Any] = field(default_factory=dict)
    task_id: str | None = None
    phase: str | None = None
    
    def get_token_count(self) -> int:
        """Get approximate token count from stats."""
        return self.stats.total_tokens
    
    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to context."""
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata from context."""
        return self.metadata.get(key, default)


@dataclass
class MiddlewareResult:
    """Result returned by middleware processing.
    
    Tells the orchestrator what action to take next.
    """
    
    action: MiddlewareAction = MiddlewareAction.CONTINUE
    message: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def continue_(cls) -> MiddlewareResult:
        """Create a CONTINUE result."""
        return cls(action=MiddlewareAction.CONTINUE)
    
    @classmethod
    def stop(cls, reason: str) -> MiddlewareResult:
        """Create a STOP result."""
        return cls(action=MiddlewareAction.STOP, reason=reason)
    
    @classmethod
    def compact(cls, metadata: dict[str, Any] | None = None) -> MiddlewareResult:
        """Create a COMPACT result."""
        return cls(
            action=MiddlewareAction.COMPACT,
            metadata=metadata or {},
        )
    
    @classmethod
    def inject(cls, message: str) -> MiddlewareResult:
        """Create an INJECT_MESSAGE result."""
        return cls(
            action=MiddlewareAction.INJECT_MESSAGE,
            message=message,
        )
    
    @classmethod
    def upstream(cls, data: dict[str, Any]) -> MiddlewareResult:
        """Create an UPSTREAM result."""
        return cls(
            action=MiddlewareAction.UPSTREAM,
            metadata={"upstream_data": data},
        )
    
    @classmethod
    def delegate(cls, agent_name: str, task: dict[str, Any]) -> MiddlewareResult:
        """Create a DELEGATE result."""
        return cls(
            action=MiddlewareAction.DELEGATE,
            metadata={"agent_name": agent_name, "task": task},
        )


class ConversationMiddleware(Protocol):
    """Protocol for middleware components.
    
    Middleware can inspect and modify the conversation context,
    and request actions from the orchestrator.
    """
    
    async def before_phase(
        self,
        context: ConversationContext,
    ) -> MiddlewareResult:
        """Called before each REACT phase.
        
        Args:
            context: Current conversation context
            
        Returns:
            MiddlewareResult indicating what action to take
        """
        ...
    
    async def after_phase(
        self,
        context: ConversationContext,
        phase_result: Any,
    ) -> MiddlewareResult:
        """Called after each REACT phase.
        
        Args:
            context: Current conversation context
            phase_result: Result from the phase execution
            
        Returns:
            MiddlewareResult indicating what action to take
        """
        ...
    
    def reset(self, reason: ResetReason = ResetReason.STOP) -> None:
        """Reset middleware state.
        
        Args:
            reason: Why the reset is occurring
        """
        ...


class TurnLimitMiddleware:
    """Middleware that limits the number of turns/phases."""
    
    def __init__(self, max_turns: int) -> None:
        self.max_turns = max_turns
        self._current_turn = 0
    
    async def before_phase(self, context: ConversationContext) -> MiddlewareResult:
        self._current_turn += 1
        
        if self._current_turn > self.max_turns:
            return MiddlewareResult.stop(
                f"Turn limit of {self.max_turns} reached"
            )
        return MiddlewareResult.continue_()
    
    async def after_phase(
        self,
        context: ConversationContext,
        phase_result: Any,
    ) -> MiddlewareResult:
        return MiddlewareResult.continue_()
    
    def reset(self, reason: ResetReason = ResetReason.STOP) -> None:
        self._current_turn = 0


class TokenLimitMiddleware:
    """Middleware that limits token usage."""
    
    def __init__(self, max_tokens: int) -> None:
        self.max_tokens = max_tokens
    
    async def before_phase(self, context: ConversationContext) -> MiddlewareResult:
        if context.get_token_count() >= self.max_tokens:
            return MiddlewareResult.compact(
                metadata={"threshold": self.max_tokens}
            )
        return MiddlewareResult.continue_()
    
    async def after_phase(
        self,
        context: ConversationContext,
        phase_result: Any,
    ) -> MiddlewareResult:
        return MiddlewareResult.continue_()
    
    def reset(self, reason: ResetReason = ResetReason.STOP) -> None:
        pass


class UpstreamMiddleware:
    """Middleware that handles upstreaming results to parent orchestrator."""
    
    def __init__(
        self,
        upstream_callback: Callable[[dict[str, Any]], None],
        batch_size: int = 10,
    ) -> None:
        self.upstream_callback = upstream_callback
        self.batch_size = batch_size
        self._pending: list[dict[str, Any]] = []
    
    async def before_phase(self, context: ConversationContext) -> MiddlewareResult:
        return MiddlewareResult.continue_()
    
    async def after_phase(
        self,
        context: ConversationContext,
        phase_result: Any,
    ) -> MiddlewareResult:
        # Check if there are results to upstream
        if phase_result and isinstance(phase_result, dict):
            self._pending.append(phase_result)
            
            # Flush if batch size reached
            if len(self._pending) >= self.batch_size:
                await self._flush()
                return MiddlewareResult.upstream(self._pending[-self.batch_size:])
        
        return MiddlewareResult.continue_()
    
    async def _flush(self) -> None:
        """Flush pending upstream events."""
        for item in self._pending:
            self.upstream_callback(item)
        self._pending.clear()
    
    def reset(self, reason: ResetReason = ResetReason.STOP) -> None:
        self._pending.clear()


class MiddlewarePipeline:
    """Pipeline for executing middleware in sequence."""
    
    def __init__(self) -> None:
        self._middlewares: list[ConversationMiddleware] = []
    
    def add(self, middleware: ConversationMiddleware) -> MiddlewarePipeline:
        """Add middleware to the pipeline."""
        self._middlewares.append(middleware)
        return self
    
    def clear(self) -> None:
        """Clear all middleware."""
        self._middlewares.clear()
    
    def reset(self, reason: ResetReason = ResetReason.STOP) -> None:
        """Reset all middleware."""
        for mw in self._middlewares:
            mw.reset(reason)
    
    async def run_before_phase(self, context: ConversationContext) -> MiddlewareResult:
        """Run all middleware before a phase.
        
        Returns the first non-CONTINUE result, or CONTINUE if all pass.
        """
        for mw in self._middlewares:
            result = await mw.before_phase(context)
            if result.action != MiddlewareAction.CONTINUE:
                return result
        return MiddlewareResult.continue_()
    
    async def run_after_phase(
        self,
        context: ConversationContext,
        phase_result: Any,
    ) -> MiddlewareResult:
        """Run all middleware after a phase."""
        for mw in self._middlewares:
            result = await mw.after_phase(context, phase_result)
            if result.action != MiddlewareAction.CONTINUE:
                return result
        return MiddlewareResult.continue_()
