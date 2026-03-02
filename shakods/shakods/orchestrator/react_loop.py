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
    ):
        self.judge = judge
        self.prompt_loader = prompt_loader
        self.max_iterations = max_iterations

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

            if state.phase == REACTPhase.REASONING:
                await self._phase_reasoning(state)
            elif state.phase == REACTPhase.EVALUATION:
                evaluation = await self.judge.evaluate_task_completion(state)
                if evaluation.is_complete and evaluation.confidence >= 0.7:
                    state.phase = REACTPhase.COMMUNICATING
                    await self._phase_communicating(state)
                    break
                state.phase = self._next_phase(state.phase)
            elif state.phase == REACTPhase.ACTING:
                await self._phase_acting(state)
            elif state.phase == REACTPhase.COMMUNICATING:
                await self._phase_communicating(state)
                break
            elif state.phase == REACTPhase.TRACKING:
                await self._phase_tracking(state)
                state.phase = REACTPhase.REASONING

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
            if task.status == "pending":
                task.status = "completed"
                task.result = {"message": "Placeholder execution"}
                state.completed_tasks.append(task)
        state.decomposed_tasks = [t for t in state.decomposed_tasks if t.status != "completed"]
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
