"""REACT (Reasoning, Evaluation, Acting, Communicating, Tracking) orchestrator loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any, Callable, Awaitable

from loguru import logger


class REACTPhase(StrEnum):
    """Phases of the REACT loop."""

    REASONING = auto()
    EVALUATION = auto()
    ACTING = auto()
    COMMUNICATING = auto()
    TRACKING = auto()


@dataclass
class DecomposedTask:
    """A single decomposed subtask."""

    task_id: str
    description: str
    agent: str | None
    status: str = "pending"  # pending, in_progress, completed, failed
    result: dict[str, Any] | None = None
    error: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)  # task params for agent.execute()


@dataclass
class REACTState:
    """State maintained across REACT loop iterations."""

    task_id: str
    original_request: str
    phase: REACTPhase = REACTPhase.REASONING
    iteration: int = 0
    max_iterations: int = 20
    decomposed_tasks: list[DecomposedTask] = field(default_factory=list)
    completed_tasks: list[DecomposedTask] = field(default_factory=list)
    failed_tasks: list[DecomposedTask] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    final_response: str | None = None


@dataclass
class REACTResult:
    """Result of a completed REACT orchestration."""

    success: bool
    state: REACTState
    message: str


class REACTOrchestrator:
    """REACT loop orchestrator coordinating specialized agents."""

    def __init__(
        self,
        judge: Any,
        prompt_loader: Any,
        max_iterations: int = 20,
        agent_registry: Any = None,
        middleware_pipeline: Any = None,
    ):
        self.judge = judge
        self.prompt_loader = prompt_loader
        self.max_iterations = max_iterations
        self.agent_registry = agent_registry
        self.middleware_pipeline = middleware_pipeline

    async def process_request(
        self,
        request: str,
        task_id: str | None = None,
        on_progress: Callable[[REACTState], Awaitable[None]] | None = None,
    ) -> REACTResult:
        """Run the REACT loop to process a request."""
        import uuid

        tid = task_id or str(uuid.uuid4())
        state = REACTState(
            task_id=tid,
            original_request=request,
            max_iterations=self.max_iterations,
        )

        try:
            state = await self._run_react_loop(state, on_progress)
            return REACTResult(
                success=state.final_response is not None,
                state=state,
                message=state.final_response or "Incomplete",
            )
        except Exception as e:
            logger.exception("REACT loop failed: %s", e)
            return REACTResult(
                success=False,
                state=state,
                message=str(e),
            )

    def _next_phase(self, phase: REACTPhase) -> REACTPhase:
        """Advance to the next phase in the loop."""
        phases = list(REACTPhase)
        idx = phases.index(phase)
        return phases[(idx + 1) % len(phases)]

    def _build_conversation_context(self, state: REACTState) -> Any:
        """Build ConversationContext from REACTState for middleware."""
        from shakods.vendor.vibe.middleware import AgentStats, ConversationContext
        messages = state.context.get("messages", [])
        if not messages and state.original_request:
            messages = [{"role": "user", "content": state.original_request[:500]}]
        phase_val = getattr(state.phase, "value", str(state.phase))
        return ConversationContext(
            messages=messages,
            stats=AgentStats(),
            metadata={"iteration": state.iteration, "task_id": state.task_id},
            task_id=state.task_id,
            phase=phase_val,
        )

    def _apply_middleware_result(self, result: Any, state: REACTState) -> bool:
        """Apply middleware result. Return True to break loop (STOP)."""
        from shakods.vendor.vibe.middleware import MiddlewareAction
        action = getattr(result, "action", None)
        if action is None:
            return False
        if action == MiddlewareAction.STOP:
            state.context["middleware_stop"] = getattr(result, "reason", "stopped")
            state.final_response = getattr(result, "reason", None) or "Stopped by middleware"
            return True
        if action == MiddlewareAction.COMPACT:
            state.context["compact_requested"] = result.metadata if hasattr(result, "metadata") else {}
            return False
        if action == MiddlewareAction.INJECT_MESSAGE and getattr(result, "message", None):
            state.context.setdefault("injected_messages", []).append(result.message)
            return False
        if action == MiddlewareAction.DELEGATE:
            meta = getattr(result, "metadata", {}) or {}
            agent_name = meta.get("agent_name")
            task_payload = meta.get("task", {})
            if agent_name and task_payload is not None:
                state.decomposed_tasks.append(
                    DecomposedTask(
                        task_id=f"delegate_{len(state.decomposed_tasks)}",
                        description=task_payload.get("description", "Delegated task"),
                        agent=agent_name,
                        status="pending",
                        payload=task_payload,
                    )
                )
            return False
        return False

    async def _run_react_loop(
        self,
        state: REACTState,
        on_progress: Callable[[REACTState], Awaitable[None]] | None,
    ) -> REACTState:
        """Execute the REACT loop until completion or max iterations."""
        while state.iteration < state.max_iterations:
            state.iteration += 1
            if on_progress:
                await on_progress(state)

            conv_ctx = self._build_conversation_context(state)
            if self.middleware_pipeline:
                before_result = await self.middleware_pipeline.run_before_phase(conv_ctx)
                if self._apply_middleware_result(before_result, state):
                    break

            phase_result = None
            if state.phase == REACTPhase.REASONING:
                await self._phase_reasoning(state)
                phase_result = {"phase": "reasoning"}
            elif state.phase == REACTPhase.EVALUATION:
                evaluation = await self.judge.evaluate_task_completion(state)
                if evaluation.is_complete and evaluation.confidence >= 0.7:
                    state.phase = REACTPhase.COMMUNICATING
                    await self._phase_communicating(state)
                    break
                state.phase = self._next_phase(state.phase)
                phase_result = {"phase": "evaluation", "evaluation": evaluation}
            elif state.phase == REACTPhase.ACTING:
                await self._phase_acting(state)
                phase_result = {"phase": "acting"}
            elif state.phase == REACTPhase.COMMUNICATING:
                await self._phase_communicating(state)
                break
            elif state.phase == REACTPhase.TRACKING:
                await self._phase_tracking(state)
                state.phase = REACTPhase.REASONING
                phase_result = {"phase": "tracking"}

            if self.middleware_pipeline and phase_result is not None:
                after_result = await self.middleware_pipeline.run_after_phase(conv_ctx, phase_result)
                if self._apply_middleware_result(after_result, state):
                    break

        return state

    async def _phase_reasoning(self, state: REACTState) -> None:
        """REASONING: Analyze request and decompose into subtasks."""
        if not state.decomposed_tasks:
            state.decomposed_tasks = [
                DecomposedTask(
                    task_id=f"t1",
                    description=state.original_request,
                    agent=None,
                    status="pending",
                )
            ]
        state.phase = self._next_phase(state.phase)

    async def _phase_evaluation(self, state: REACTState) -> None:
        """EVALUATION: Assess current state against goals."""
        state.phase = self._next_phase(state.phase)

    async def _phase_acting(self, state: REACTState) -> None:
        """ACTING: Delegate to specialized agents."""
        for task in state.decomposed_tasks:
            if task.status != "pending":
                continue
            task.status = "in_progress"
            if self.agent_registry:
                task_dict = {**task.payload, "description": task.description}
                agent = self.agent_registry.get_agent_for_task(task_dict)
                if agent:
                    try:
                        task.result = await agent.execute(task_dict, upstream_callback=None)
                        task.status = "completed"
                    except Exception as e:
                        logger.exception("Agent execution failed: %s", e)
                        task.status = "failed"
                        task.error = str(e)
                        task.result = {"error": str(e)}
                        state.failed_tasks.append(task)
                else:
                    task.status = "completed"
                    task.result = {"message": "No agent for task", "description": task.description}
            else:
                task.status = "completed"
                task.result = {"message": "Placeholder execution (no agent registry)"}
            if task.status == "completed":
                state.completed_tasks.append(task)
        state.decomposed_tasks = [
            t for t in state.decomposed_tasks
            if t.status not in ("completed", "failed")
        ]
        state.phase = self._next_phase(state.phase)

    async def _phase_communicating(self, state: REACTState) -> None:
        """COMMUNICATING: Report progress and final response."""
        state.final_response = (
            f"Processed: {state.original_request[:100]}... "
            f"({len(state.completed_tasks)} completed)"
        )

    async def _phase_tracking(self, state: REACTState) -> None:
        """TRACKING: Update state and maintain context."""
        state.context["last_iteration"] = state.iteration
