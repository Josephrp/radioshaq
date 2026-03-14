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
        memory_manager: Any = None,
        db: Any = None,
    ):
        self.judge = judge
        self.prompt_loader = prompt_loader
        self.max_iterations = max_iterations
        self.agent_registry = agent_registry
        self.middleware_pipeline = middleware_pipeline
        self.tool_registry = tool_registry
        self.llm_client = llm_client
        self.memory_manager = memory_manager
        self.db = db

    async def process_request(
        self,
        request: str,
        task_id: str | None = None,
        callsign: str | None = None,
        on_progress: Callable[[REACTState], Awaitable[None]] | None = None,
        inbound_metadata: dict[str, Any] | None = None,
    ) -> REACTResult:
        """Run the REACT loop to process a request. If callsign and memory_manager are set, load memory context and persist/retain after success."""
        import asyncio
        import uuid
        from zoneinfo import ZoneInfo

        tid = task_id or str(uuid.uuid4())
        state = REACTState(
            task_id=tid,
            original_request=request,
            max_iterations=self.max_iterations,
        )
        state.context["inbound_metadata"] = inbound_metadata or {}

        # Load whitelisted callsign bands (preferred_bands, last_band) for relay/context
        callsign_repo = getattr(self, "_callsign_repository", None)
        if callsign_repo is not None and hasattr(callsign_repo, "list_registered"):
            try:
                registered = await callsign_repo.list_registered()
                state.context["whitelisted_callsign_bands"] = {
                    (cs.get("callsign") or str(cs)): {
                        "last_band": cs.get("last_band"),
                        "preferred_bands": cs.get("preferred_bands") or [],
                    }
                    for cs in registered
                    if cs.get("callsign")
                }
            except Exception as e:
                logger.debug("Load whitelisted_callsign_bands failed: {}", e)
                state.context["whitelisted_callsign_bands"] = {}
        else:
            state.context["whitelisted_callsign_bands"] = {}

        # Load memory context before loop when callsign and memory_manager are set
        if callsign and self.memory_manager:
            try:
                from radioshaq.memory import build_memory_context
                mem_cfg = getattr(getattr(self, "_config", None), "memory", None)
                recent_limit = getattr(mem_cfg, "recent_messages_limit", 40)
                summary_days = getattr(mem_cfg, "daily_summary_days", 7)
                tz_str = getattr(mem_cfg, "summary_timezone", "America/New_York")
                tz = ZoneInfo(tz_str)
                ctx = await build_memory_context(
                    self.memory_manager,
                    callsign,
                    recent_limit=recent_limit,
                    summary_days=summary_days,
                    timezone=tz,
                )
                state.context["memory_system_prefix"] = ctx.get("system_prefix", "")
                state.context["memory_messages"] = ctx.get("messages", [])
                state.context["memory_metadata"] = ctx.get("metadata", {})
                state.context["callsign"] = callsign
                # Last N + current user message for middleware/judge
                messages = list(ctx.get("messages", []))
                messages.append({"role": "user", "content": request})
                state.context["messages"] = messages
            except Exception as e:
                logger.warning("Memory context load failed: {}", e)

        try:
            state = await self._run_react_loop(state, on_progress)
            # Persist and retain after success
            if callsign and self.memory_manager and state.final_response is not None:
                try:
                    await self.memory_manager.append_messages(
                        callsign,
                        [
                            ("user", request, None, None),
                            ("assistant", state.final_response, None, None),
                        ],
                    )
                except Exception as e:
                    logger.warning("Memory append_messages failed: {}", e)
                try:
                    from radioshaq.memory.hindsight import retain_exchange
                    from radioshaq.config.resolve import get_memory_config_for_role
                    memory_config = getattr(self, "_config", None) and get_memory_config_for_role(self._config, "orchestrator")
                    await asyncio.to_thread(
                        retain_exchange,
                        callsign,
                        request,
                        state.final_response,
                        config=memory_config,
                    )
                except Exception as e:
                    logger.debug("Hindsight retain failed (non-fatal): {}", e)
            return REACTResult(
                success=state.final_response is not None,
                state=state,
                message=state.final_response or "Incomplete",
            )
        except Exception as e:
            logger.exception("REACT loop failed: {}", e)
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
            logger.warning("Parse decomposed tasks failed: {}", e)
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

    def _build_phase_context(self, state: REACTState) -> dict[str, str]:
        """Build context dict for prompt loader: inbound_metadata_summary, callsign_bands_summary, and phase placeholders."""
        ctx = state.context
        inbound = ctx.get("inbound_metadata") or {}
        if isinstance(inbound, dict) and inbound:
            parts = [f"Band: {inbound.get('band', '')}", f"frequency_hz: {inbound.get('frequency_hz')}"]
            if inbound.get("destination_callsign"):
                parts.append(f"destination_callsign: {inbound['destination_callsign']}")
            inbound_metadata_summary = "**Radio (radio_rx) inbound:** " + ", ".join(str(p) for p in parts) + "\n"
        else:
            inbound_metadata_summary = ""

        bands = ctx.get("whitelisted_callsign_bands") or {}
        if isinstance(bands, dict) and bands:
            lines = [
                f"{cs}: last_band={info.get('last_band') or '-'} preferred={info.get('preferred_bands') or []}"
                for cs, info in bands.items()
            ]
            callsign_bands_summary = "**Callsign bands:** " + "; ".join(lines) + "\n"
        else:
            callsign_bands_summary = ""

        return {
            "current_phase": getattr(state, "phase", "REASONING") or "REASONING",
            "task_id": state.task_id,
            "iteration": str(state.iteration),
            "max_iterations": str(self.max_iterations),
            "runtime_context": "",
            "inbound_metadata_summary": inbound_metadata_summary,
            "callsign_bands_summary": callsign_bands_summary,
            "active_tasks": "",
            "completed_tasks": "",
            "upstream_memories": "",
        }

    def _inject_memory_into_system(self, state: REACTState, system_content: str) -> str:
        """Prepend memory context (core blocks, summaries, time) to system prompt when available."""
        prefix = state.context.get("memory_system_prefix", "").strip()
        if not prefix:
            return system_content
        return f"{prefix}\n\n---\n\n{system_content}"

    def _first_contact_hint(self, state: REACTState) -> str:
        """Return a one-line hint when this appears to be first contact (no prior messages)."""
        messages = state.context.get("memory_messages", [])
        if messages:
            return ""
        return (
            "[First contact: no prior conversation with this operator in context. "
            "Respond with a brief welcome, identify as the station, and offer help (relay, info, whitelist).] "
        )

    def _inject_agent_context(self, state: REACTState, task_dict: dict[str, Any]) -> None:
        """Inject request-level context (callsign, station_callsign, original_request) into task_dict for agents that need it."""
        ctx = state.context
        callsign = ctx.get("callsign")
        original = state.original_request or ""
        agent_name = (task_dict.get("agent") or "").strip() or None

        if not agent_name:
            return

        config = getattr(self, "_config", None)
        if config and agent_name == "whitelist" and not (task_dict.get("station_callsign") or "").strip():
            # Inject this station's callsign so whitelist can identify in replies (e.g. "This is K5ABC. You're approved.")
            field_cfg = getattr(config, "field", None)
            radio_cfg = getattr(config, "radio", None)
            station = (
                (getattr(field_cfg, "callsign", None) if field_cfg else None)
                or (getattr(radio_cfg, "station_callsign", None) if radio_cfg else None)
                or (getattr(radio_cfg, "packet_callsign", None) if radio_cfg else None)
            )
            if station and str(station).strip():
                task_dict["station_callsign"] = str(station).strip().upper()

        # Agents that use callsign: inject when payload doesn't already have it
        if callsign and isinstance(callsign, str) and callsign.strip():
            cs = callsign.strip().upper()
            if agent_name == "whitelist" and not (task_dict.get("callsign") or "").strip():
                task_dict["callsign"] = cs
            if agent_name == "gis" and not (task_dict.get("callsign") or "").strip():
                task_dict["callsign"] = cs
            if agent_name == "scheduler" and not (task_dict.get("initiator_callsign") or "").strip():
                task_dict["initiator_callsign"] = cs

        # Whitelist: ensure it has request text (description or request_text or message)
        if agent_name == "whitelist" and original:
            has_text = (
                (task_dict.get("request_text") or "").strip()
                or (task_dict.get("message") or "").strip()
            )
            if not has_text:
                task_dict["request_text"] = original

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
                    phase_ctx = self._build_phase_context(state)
                    system_content = self.prompt_loader.load_for_phase("reasoning", **phase_ctx)
            except Exception:
                pass
            system_content = self._inject_memory_into_system(state, system_content)
            user_content = state.original_request
            first_contact = self._first_contact_hint(state)
            if first_contact:
                user_content = first_contact + user_content
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
                logger.warning("Plan LLM call failed: {}", e)
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
                        phase_ctx = self._build_phase_context(state)
                        system_content = self.prompt_loader.load_for_phase("reasoning", **phase_ctx) or system_content
                except Exception:
                    pass
                system_content = self._inject_memory_into_system(state, system_content)
                # Conversation history: last N turns so the LLM has context (first-contact handled via memory)
                memory_messages = state.context.get("memory_messages", [])
                max_history = 20
                recent = memory_messages[-max_history:] if len(memory_messages) > max_history else memory_messages
                chat_turns: list[dict[str, Any]] = [
                    {"role": m.get("role", "user"), "content": (m.get("content") or "").strip() or "(empty)"}
                    for m in recent
                    if m.get("role") in ("user", "assistant")
                ]
                chat_turns.append({"role": "user", "content": state.original_request})
                messages = [{"role": "system", "content": system_content}]
                messages.extend(chat_turns)
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
                        if tc.name in ("recall_memory", "reflect_memory") and state.context.get("callsign"):
                            arguments_dict = {**arguments_dict, "callsign": state.context["callsign"]}
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
                # Inject request context for agents that need it (when planner omits from payload)
                self._inject_agent_context(state, task_dict)
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
                        logger.exception("Agent execution failed: {}", e)
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
        """COMMUNICATING: Set final_response from last_llm_reply, then completed_tasks, then fallback. Optionally wrap in radio format."""
        if state.final_response is not None:
            return
        state.final_response = state.context.get("last_llm_reply")
        if state.final_response:
            self._apply_radio_format(state)
            return
        for task in reversed(state.completed_tasks):
            if task.result and isinstance(task.result, dict):
                msg = task.result.get("message_for_user") or task.result.get("reason")
                if msg:
                    state.final_response = msg
                    self._apply_radio_format(state)
                    return
        state.final_response = (
            f"Processed: {state.original_request[:100]}... "
            f"({len(state.completed_tasks)} completed)"
        )
        self._apply_radio_format(state)

    def _apply_radio_format(self, state: REACTState) -> None:
        """If config enables it, wrap final_response in radio format (call-out and sign-off)."""
        config = getattr(self, "_config", None)
        if not config or not getattr(getattr(config, "radio", None), "response_radio_format_enabled", False):
            return
        if not state.final_response:
            return
        from radioshaq.orchestrator.radio_format import format_response_for_radio
        radio_cfg = config.radio
        style = getattr(radio_cfg, "response_radio_format_style", "over") or "over"
        if style == "none":
            return
        # Prefer field.callsign (station identity from setup), then radio.station_callsign, then packet_callsign
        field_cfg = getattr(config, "field", None)
        station = (
            (getattr(field_cfg, "callsign", None) if field_cfg else None)
            or getattr(radio_cfg, "station_callsign", None)
            or getattr(radio_cfg, "packet_callsign", None)
        )
        if station:
            station = (station or "").strip().upper() or None
        caller = state.context.get("callsign")
        state.final_response = format_response_for_radio(
            state.final_response,
            caller_callsign=caller,
            station_callsign=station,
            style=style,
        )

    async def _phase_tracking(self, state: REACTState) -> None:
        """TRACKING: Update state and maintain context."""
        state.context["last_iteration"] = state.iteration
