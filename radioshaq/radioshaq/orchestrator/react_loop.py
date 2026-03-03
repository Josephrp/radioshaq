"""REACT (Reasoning, Evaluation, Acting, Communicating, Tracking) orchestrator loop."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum, auto
from typing import Any, Callable, Awaitable

from loguru import logger


def _extract_json_from_text(text: str) -> str | None:
    """Extract JSON object from text (handles markdown code blocks)."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if match:
        return match.group(1)
    match = re.search(r"(\{[\s\S]*\})", text)
    if match:
        return match.group(1)
    return None


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
        tool_registry: Any = None,
        llm_client: Any = None,
    ):
        self.judge = judge
        self.prompt_loader = prompt_loader
        self.max_iterations = max_iterations
        self.agent_registry = agent_registry
        self.middleware_pipeline = middleware_pipeline
        self.tool_registry = tool_registry
        self.llm_client = llm_client

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

    def _parse_decomposed_tasks_from_llm(
        self, content: str, original_request: str
    ) -> list[DecomposedTask]:
        """Parse LLM plan output into DecomposedTask list. On failure returns single task."""
        json_str = _extract_json_from_text(content)
        if not json_str:
            return [
                DecomposedTask(
                    task_id="t1",
                    description=original_request,
                    agent=None,
                    status="pending",
                )
            ]
        try:
            data = json.loads(json_str)
            tasks_data = data.get("decomposed_tasks", [])
            if not isinstance(tasks_data, list) or not tasks_data:
                return [
                    DecomposedTask(
                        task_id="t1",
                        description=original_request,
                        agent=None,
                        status="pending",
                    )
                ]
            out: list[DecomposedTask] = []
            for i, t in enumerate(tasks_data):
                if not isinstance(t, dict):
                    continue
                task_id = str(t.get("id", f"task_{i}"))
                description = str(t.get("description", original_request))
                agent = t.get("agent")
                agent = str(agent) if agent is not None else None
                payload = t.get("payload")
                if not isinstance(payload, dict):
                    payload = {}
                out.append(
                    DecomposedTask(
                        task_id=task_id,
                        description=description,
                        agent=agent,
                        status="pending",
                        payload=payload,
                    )
                )
            return out if out else [
                DecomposedTask(
                    task_id="t1",
                    description=original_request,
                    agent=None,
                    status="pending",
                )
            ]
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning("Parse decomposed tasks failed: %s", e)
            return [
                DecomposedTask(
                    task_id="t1",
                    description=original_request,
                    agent=None,
                    status="pending",
                )
            ]

    def _build_conversation_context(self, state: REACTState) -> Any:
        """Build ConversationContext from REACTState for middleware."""
        from radioshaq.vendor.vibe.middleware import AgentStats, ConversationContext
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
        from radioshaq.vendor.vibe.middleware import MiddlewareAction
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
                state.context["last_evaluation"] = {
                    "missing_elements": evaluation.missing_elements,
                    "next_action": evaluation.next_action,
                    "reasoning": evaluation.reasoning,
                    "is_complete": evaluation.is_complete,
                    "confidence": evaluation.confidence,
                }
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
        """REASONING: Stage A plan/decompose via LLM; Stage B optional tool-calling. No short-circuit to COMMUNICATING."""
        # Stage A — Plan/Decompose: produce decomposed_tasks (when llm_client available)
        if self.llm_client:
            system_content = (
                "You are the orchestrator. Analyze the request and output a JSON plan with 'decomposed_tasks' array. "
                "Each task: id, description, agent (optional), payload (optional)."
            )
            try:
                if self.prompt_loader:
                    system_content = self.prompt_loader.load_for_phase("reasoning")
            except Exception:
                pass
            user_content = state.original_request
            last_ev = state.context.get("last_evaluation")
            if last_ev:
                missing = last_ev.get("missing_elements", []) if isinstance(last_ev, dict) else getattr(last_ev, "missing_elements", [])
                next_act = last_ev.get("next_action") if isinstance(last_ev, dict) else getattr(last_ev, "next_action", None)
                if missing or next_act:
                    user_content += "\n\nPrevious evaluation: "
                    if missing:
                        user_content += f"Missing elements: {missing}. "
                    if next_act:
                        user_content += f"Next action: {next_act}."
            plan_messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ]
            try:
                plan_response = await self.llm_client.chat(plan_messages)
                content = getattr(plan_response, "content", "") or ""
                state.decomposed_tasks = self._parse_decomposed_tasks_from_llm(
                    content, state.original_request
                )
            except Exception as e:
                logger.warning("Plan LLM call failed: %s", e)
                state.decomposed_tasks = [
                    DecomposedTask(
                        task_id="t1",
                        description=state.original_request,
                        agent=None,
                        status="pending",
                    )
                ]
            # Stage B — Optional tool-calling round(s); store last reply, do not set final_response
            if self.tool_registry and self.llm_client:
                system_content = (
                    "You are the orchestrator. Use the provided tools to fulfill the user request. "
                    "When done, reply with a short final message for the user (suitable for TTS)."
                )
                try:
                    if self.prompt_loader:
                        system_content = self.prompt_loader.load_for_phase("reasoning") or system_content
                except Exception:
                    pass
                messages: list[dict[str, Any]] = [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": state.original_request},
                ]
                tool_definitions = self.tool_registry.get_definitions()
                max_tool_rounds = 10
                last_content = ""
                for _round in range(max_tool_rounds):
                    response = await self.llm_client.chat_with_tools(
                        messages, tools=tool_definitions
                    )
                    last_content = (response.content or "").strip()
                    tool_calls = getattr(response, "tool_calls", None) or []
                    if not tool_calls:
                        state.context["last_llm_reply"] = last_content or state.context.get("last_llm_reply")
                        state.context["llm_messages"] = messages
                        state.phase = self._next_phase(state.phase)
                        return
                    assistant_msg: dict[str, Any] = {"role": "assistant", "content": last_content or None}
                    assistant_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": tc.arguments},
                        }
                        for tc in tool_calls
                    ]
                    messages.append(assistant_msg)
                    for tc in tool_calls:
                        args_str = tc.arguments or "{}"
                        try:
                            arguments_dict = json.loads(args_str)
                        except json.JSONDecodeError:
                            arguments_dict = {}
                        try:
                            result = await self.tool_registry.execute(tc.name, arguments_dict)
                        except Exception as e:
                            result = f"Error: {e}"
                        messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(result)})
                state.context["last_llm_reply"] = last_content or "Tool limit reached."
                state.context["llm_messages"] = messages
                state.phase = self._next_phase(state.phase)
                return
            # No tool registry: advance to next phase after Stage A
            state.phase = self._next_phase(state.phase)
            return
        # No LLM: fallback single task
        if not state.decomposed_tasks:
            state.decomposed_tasks = [
                DecomposedTask(
                    task_id="t1",
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
        """ACTING: Delegate to specialized agents; subtask judge after each run; retry when retry_eligible."""
        from radioshaq.middleware.upstream import UpstreamEvent

        MAX_SUBTASK_RETRIES = 1

        async def upstream_callback(ev: UpstreamEvent) -> None:
            state.context.setdefault("upstream_events", []).append(
                {"source": ev.source, "event_type": ev.event_type, "payload": ev.payload}
            )

        for task in state.decomposed_tasks:
            if task.status != "pending":
                continue
            task.status = "in_progress"
            if self.agent_registry:
                task_dict = {
                    **task.payload,
                    "description": task.description,
                    "agent": task.agent,
                }
                agent = self.agent_registry.get_agent_for_task(task_dict)
                if agent:
                    try:
                        task.result = await agent.execute(
                            task_dict, upstream_callback=upstream_callback
                        )
                        task.status = "completed"
                        task.error = None
                        subtask_eval = await self.judge.evaluate_subtask(
                            task.task_id, task.description, task.result, None
                        )
                        state.context.setdefault("subtask_evaluations", []).append(
                            {"task_id": task.task_id, "retry_eligible": subtask_eval.retry_eligible}
                        )
                        if (
                            subtask_eval.retry_eligible
                            and task.payload.get("_retries", 0) < MAX_SUBTASK_RETRIES
                        ):
                            task.status = "pending"
                            task.payload["_retries"] = task.payload.get("_retries", 0) + 1
                            task.result = None
                    except Exception as e:
                        logger.exception("Agent execution failed: %s", e)
                        task.error = str(e)
                        task.result = {"error": str(e)}
                        subtask_eval = await self.judge.evaluate_subtask(
                            task.task_id, task.description, None, str(e)
                        )
                        state.context.setdefault("subtask_evaluations", []).append(
                            {"task_id": task.task_id, "retry_eligible": subtask_eval.retry_eligible}
                        )
                        if (
                            subtask_eval.retry_eligible
                            and task.payload.get("_retries", 0) < MAX_SUBTASK_RETRIES
                        ):
                            task.status = "pending"
                            task.payload["_retries"] = task.payload.get("_retries", 0) + 1
                            task.error = None
                            task.result = None
                        else:
                            task.status = "failed"
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
        """COMMUNICATING: Set final_response from last_llm_reply, then completed_tasks, then fallback."""
        if state.final_response is not None:
            return
        state.final_response = state.context.get("last_llm_reply")
        if state.final_response:
            return
        for task in reversed(state.completed_tasks):
            if task.result and isinstance(task.result, dict):
                msg = task.result.get("message_for_user") or task.result.get("reason")
                if msg:
                    state.final_response = msg
                    return
        state.final_response = (
            f"Processed: {state.original_request[:100]}... "
            f"({len(state.completed_tasks)} completed)"
        )

    async def _phase_tracking(self, state: REACTState) -> None:
        """TRACKING: Update state and maintain context."""
        state.context["last_iteration"] = state.iteration
