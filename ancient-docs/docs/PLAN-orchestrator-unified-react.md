# Plan: Unify Orchestrator — Full REACT Loop with Tools, Judge, and Agents

This plan wires the radioshaq orchestrator so that **one path** supports both LLM tool-calling and the full REACT loop (REASONING → EVALUATION → ACTING → COMMUNICATING → TRACKING), with the Judge, subtask judge, and agent registry used in the same flow as the API and whitelist.

---

## Current State (Summary)

| Component | Current behavior |
|-----------|------------------|
| **REACT loop** | When `tool_registry` and `llm_client` are set (default in server): REASONING runs an LLM tool-calling loop (up to 10 rounds), then jumps to COMMUNICATING. EVALUATION, ACTING, TRACKING never run. |
| **Agent path** | When tools are not set: REASONING creates one task (whole request), then EVALUATION → ACTING → COMMUNICATING → TRACKING. Judge used in EVALUATION; agents run in ACTING. |
| **Judge** | `evaluate_task_completion()` used only in agent path. `evaluate_subtask()` never called from the loop. |
| **Whitelist** | `/whitelist-request` expects `completed_tasks` with `agent == "whitelist"`; with tools enabled ACTING never runs, so that branch is dead. Useful behavior is LLM + register_callsign tool + final_response. |
| **Middleware** | TurnLimit and TokenLimit only. DELEGATE/INJECT/COMPACT implemented in `_apply_middleware_result` but no middleware returns them. |

**Goal:** Single flow where the orchestrator can plan (decompose), act (tools and/or agents), evaluate (task + subtask judges), and iterate until the Judge says done or max iterations.

---

## Architecture (Target)

```mermaid
flowchart LR
  subgraph entry [Entry]
    API["/process\n/whitelist-request"]
    Bus["MessageBus\nconsumer"]
  end
  subgraph loop [Unified REACT Loop]
    R[REASONING]
    E[EVALUATION]
    A[ACTING]
    C[COMMUNICATING]
    T[TRACKING]
    R --> E
    E -->|not done| A
    A --> E
    E -->|done| C
    C --> end
    A --> T
    T --> R
  end
  subgraph reasoning [REASONING]
    Plan["Plan/Decompose\n(LLM or structured)"]
    Tools["Tool-calling\n(optional round)"]
  end
  subgraph acting [ACTING]
    Registry["AgentRegistry"]
    ToolExec["ToolRegistry\nexecute"]
  end
  subgraph judge [Evaluation]
    TaskJudge["Task Judge"]
    SubtaskJudge["Subtask Judge"]
  end
  entry --> R
  R --> Plan
  Plan --> Decomposed[DecomposedTask list]
  Decomposed --> E
  E --> TaskJudge
  TaskJudge --> A
  A --> Registry
  A --> ToolExec
  Registry --> SubtaskJudge
  SubtaskJudge --> E
```

---

## Projects and Activities

### Project 1: Single REACT Path (Unify Tool vs Agent Branch)

**Objective:** One loop that always runs REASONING → EVALUATION → ACTING → … with a clear contract: REASONING produces/updates `decomposed_tasks` and optionally runs tool rounds; ACTING runs both agents and tools; EVALUATION uses the Judge.

#### Activity 1.1 — REASONING: Plan-then-optional-tools

- **File:** [radioshaq/radioshaq/orchestrator/react_loop.py](radioshaq/radioshaq/orchestrator/react_loop.py)
- **Tasks:**
  1. **Refactor `_phase_reasoning`** so it has two stages (both run when `llm_client` is available):
     - **Stage A — Plan/Decompose:** Call LLM (or a structured planner) with prompt from `prompts/orchestrator/phases/reasoning.md` to produce a list of `DecomposedTask` (id, description, agent/capability, payload). Parse JSON from the prompt’s output format and map to `state.decomposed_tasks`. If no LLM or parse fails, fallback: single task with `description = state.original_request`, `agent = None`.
     - **Stage B — Optional tool round:** If `tool_registry` and `llm_client` are set and config/flag allows, run one tool-calling round (or a small number of rounds) so the LLM can perform immediate actions (e.g. send_audio_over_radio, register_callsign). Append any “delegate” outcomes from tools to `state.decomposed_tasks` (e.g. a tool that enqueues an agent task). Do not set `state.final_response` in REASONING; leave that to COMMUNICATING.
  2. **Stop short-circuiting to COMMUNICATING from REASONING.** Remove the early `state.phase = REACTPhase.COMMUNICATING; return` after the tool loop. Instead, set `state.phase = self._next_phase(state.phase)` so the loop proceeds to EVALUATION (and then ACTING if needed).
  3. **Context for planning:** Pass into the plan prompt: `state.original_request`, `state.context` (e.g. injected_messages, last_iteration), and optionally a summary of `completed_tasks` / `failed_tasks` so the LLM can do multi-step planning.
- **Subtasks (line-level):**
  - In `_phase_reasoning`, after building `messages` for the tool loop: add a first “plan” step that calls the LLM with the reasoning prompt and parses `decomposed_tasks` into `state.decomposed_tasks` (merge or replace by config).
  - Replace the block that sets `state.final_response = last_content or ...` and `return` with: store `last_content` in `state.context["last_llm_reply"]` for COMMUNICATING, then `state.phase = self._next_phase(state.phase)` and return.
  - Ensure when no tools are used, Stage A only runs and still advances phase to EVALUATION.

#### Activity 1.2 — ACTING: Run agents and optional tools

- **File:** [radioshaq/radioshaq/orchestrator/react_loop.py](radioshaq/radioshaq/orchestrator/react_loop.py)
- **Tasks:**
  1. **Keep `_phase_acting` as the single place that executes `state.decomposed_tasks`** via `AgentRegistry` (existing logic). Ensure tasks with `agent` set run through `get_agent_for_task` and `agent.execute()`.
  2. **Optional: Support “tool” tasks.** If a `DecomposedTask` has a special marker (e.g. `payload.get("_tool")`) or `agent == "_tool"`, execute via `tool_registry.execute(tool_name, payload)` instead of the registry. This allows the planner to emit both “run agent X” and “call tool Y” as tasks.
  3. **Subtask judge after each agent run:** After each successful or failed agent execution, call `judge.evaluate_subtask(task.task_id, task.description, task.result, task.error)` and store the result on the task or in context. Use `retry_eligible` to optionally re-queue the task or mark for retry (implementation detail: append a new task or set status back to pending with a retry cap).
- **Subtasks (line-level):**
  - In `_phase_acting`, after `task.result = await agent.execute(...)` (and in the `except` branch for `task.error`), add: `subtask_eval = await self.judge.evaluate_subtask(task.task_id, task.description, task.result, task.error)`; attach to `task` or `state.context["subtask_evaluations"]`.
  - If `subtask_eval.retry_eligible` and retry count below a limit, re-append a clone of the task with status `pending` (or a new task_id) so it runs again in a later ACTING phase.
  - If implementing tool-in-ACTING: in the loop over `state.decomposed_tasks`, branch on `task.agent == "_tool"` (or payload marker) and call `tool_registry.execute(...)`; then apply subtask judge the same way.

#### Activity 1.3 — EVALUATION: Always run Judge after REASONING/ACTING

- **File:** [radioshaq/radioshaq/orchestrator/react_loop.py](radioshaq/radioshaq/orchestrator/react_loop.py)
- **Tasks:**
  1. **Ensure EVALUATION runs in the unified path.** In `_run_react_loop`, when `state.phase == REACTPhase.EVALUATION`, call `self.judge.evaluate_task_completion(state)` (already done). Use evaluation to decide:
     - If `evaluation.is_complete and evaluation.confidence >= threshold`: go to COMMUNICATING and break.
     - Else: set `state.context["last_evaluation"] = evaluation` (missing_elements, next_action), then advance to ACTING (so ACTING can process remaining or new tasks).
  2. **Feed Judge with full context.** Ensure `_build_task_evaluation_prompt` (in judge) receives updated `state.decomposed_tasks`, `completed_tasks`, `failed_tasks`, and `state.context` (including subtask evaluations if stored). Judge already gets these via `state`; no change needed in judge.py if state is populated.
  3. **Use `next_action` / `missing_elements` for next REASONING.** When transitioning TRACKING → REASONING, pass `state.context.get("last_evaluation")` into the next REASONING so the planner can see what’s missing and produce follow-up tasks.
- **Subtasks (line-level):**
  - In `_run_react_loop`, EVALUATION branch: after `evaluation = await self.judge.evaluate_task_completion(state)`, set `state.context["last_evaluation"] = evaluation` (or a serializable form) before advancing phase.
  - In `_phase_tracking`, ensure `state.context["last_evaluation"]` is preserved and available for the next REASONING.
  - In `_phase_reasoning` (Stage A), when building the plan prompt, add a variable `missing_elements` and `next_action` from `state.context.get("last_evaluation")` so the LLM can refine the plan.

#### Activity 1.4 — COMMUNICATING: Final message from state

- **File:** [radioshaq/radioshaq/orchestrator/react_loop.py](radioshaq/radioshaq/orchestrator/react_loop.py)
- **Tasks:**
  1. **Compute `state.final_response` from multiple sources:** (1) `state.context.get("last_llm_reply")` (from tool-calling or plan step), (2) first `message_for_user` / `reason` from `state.completed_tasks`, (3) fallback string. Use this in `_phase_communicating` so that when we exit via EVALUATION→COMMUNICATING, the user gets a proper message.
  2. **Whitelist compatibility:** When the flow used tools (e.g. register_callsign), `final_response` is already the LLM’s reply. When the flow used agents, a completed task with `agent == "whitelist"` can still provide `message_for_user`. Ensure `_phase_communicating` aggregates these so `/whitelist-request` can use `result.message` and optionally `result.state.completed_tasks` for `approved` / `message_for_user`.
- **Subtasks (line-level):**
  - In `_phase_communicating`, first set `state.final_response = state.context.get("last_llm_reply")`; then if still None, iterate `reversed(state.completed_tasks)` for `message_for_user` / `reason`; then fallback to the existing “Processed: …” string.
  - No change required in [radioshaq/radioshaq/api/routes/messages.py](radioshaq/radioshaq/api/routes/messages.py) if `result.message` and `result.state.completed_tasks` remain the contract; document that for whitelist, either `result.message` or a whitelist task result can carry the user message.

---

### Project 2: Decomposition and Planner Contract

**Objective:** REASONING produces a list of `DecomposedTask` with a stable schema; support LLM-based and (future) structured planner.

#### Activity 2.1 — Decomposition prompt and parsing

- **Files:** [radioshaq/prompts/orchestrator/phases/reasoning.md](radioshaq/prompts/orchestrator/phases/reasoning.md), [radioshaq/radioshaq/orchestrator/react_loop.py](radioshaq/radioshaq/orchestrator/react_loop.py)
- **Tasks:**
  1. **Extend reasoning.md** so the “Output Format” is the single contract: JSON with `decomposed_tasks` array; each element has `id`, `description`, `agent` (or `capability`), optional `payload`, `dependencies`, `success_criteria`. Add one sentence: “If the request can be fulfilled entirely by tools (e.g. send a message, register a callsign), you may output a single step that indicates using tools; the system will then run tool-calling.”
  2. **Add a parser** in `react_loop.py`: `_parse_decomposed_tasks_from_llm(content: str) -> list[DecomposedTask]`. Use existing JSON extraction (e.g. from judge or a shared util), map keys to `DecomposedTask(task_id, description, agent, status="pending", payload=...)`. On parse failure, return a single task with `description = original_request`.
  3. **Call parser from REASONING:** After the “plan” LLM call in Stage A, get content from the response, call `_parse_decomposed_tasks_from_llm`, and set `state.decomposed_tasks = parsed` (or merge with existing by config).
- **Subtasks (line-level):**
  - In [radioshaq/prompts/orchestrator/phases/reasoning.md](radioshaq/prompts/orchestrator/phases/reasoning.md): add `capability` and `payload` to the example JSON; add the sentence about tools.
  - In `react_loop.py`: add `def _parse_decomposed_tasks_from_llm(self, content: str, original_request: str) -> list[DecomposedTask]` (reuse `_extract_json`-style logic from judge or a small shared helper).
  - In `_phase_reasoning` Stage A: after LLM response, `state.decomposed_tasks = self._parse_decomposed_tasks_from_llm(response.content, state.original_request)`.

#### Activity 2.2 — Agent/capability mapping

- **File:** [radioshaq/radioshaq/orchestrator/registry.py](radioshaq/radioshaq/orchestrator/registry.py)
- **Tasks:**
  1. **Document** that `DecomposedTask.agent` can be the exact agent name from `AgentRegistry` (e.g. `radio_tx`, `whitelist`, `sms`, `gis_agent`), or leave None for capability-based lookup via `get_agent_for_task` using `description` and `payload`.
  2. **No code change required** if `_phase_acting` already passes `{**task.payload, "description": task.description, "agent": task.agent}` to `get_agent_for_task`; verify and add a test that a task with `agent="whitelist"` routes to WhitelistAgent.

---

### Project 3: Judge and Quality in the Loop

**Objective:** Task Judge drives “done vs continue”; Subtask Judge runs after each agent execution and can trigger retries.

#### Activity 3.1 — Task Judge in EVALUATION (already used)

- **File:** [radioshaq/radioshaq/orchestrator/react_loop.py](radioshaq/radioshaq/orchestrator/react_loop.py)
- **Tasks:**
  1. **Keep** the existing EVALUATION branch that calls `self.judge.evaluate_task_completion(state)` and branches on `is_complete` and `confidence >= 0.7` to either go to COMMUNICATING or to ACTING.
  2. **Persist evaluation in context** (see Activity 1.3) so TRACKING and next REASONING can use `missing_elements` and `next_action`.

#### Activity 3.2 — Subtask Judge after each agent run

- **File:** [radioshaq/radioshaq/orchestrator/react_loop.py](radioshaq/radioshaq/orchestrator/react_loop.py)
- **Tasks:**
  1. **Call `judge.evaluate_subtask`** in `_phase_acting` after each agent execute (see Activity 1.2). Store `SubtaskEvaluation` in `state.context.setdefault("subtask_evaluations", []).append(...)` or on the task object (e.g. add `task.subtask_evaluation` if we extend the dataclass).
  2. **Retry logic:** If `subtask_eval.retry_eligible` and a per-task retry count (e.g. in `task.payload["_retries"]`) is below max (e.g. 1), re-queue the task: set `task.status = "pending"` and do not move it to `completed_tasks`; or append a new DecomposedTask with the same description/agent and increment retry in payload. Cap total retries to avoid infinite loops.
- **Subtasks (line-level):**
  - In `_phase_acting`, after `task.result = await agent.execute(...)`: `subtask_eval = await self.judge.evaluate_subtask(task.task_id, task.description, task.result, None)`; store on task or in context.
  - In the `except` block: `subtask_eval = await self.judge.evaluate_subtask(task.task_id, task.description, None, str(e))`; same storage.
  - Add a retry cap (e.g. 1) and, when `retry_eligible` and under cap, set `task.status = "pending"` and skip moving to `completed_tasks`; next iteration will pick it up again (or re-append with incremented retry count).

#### Activity 3.3 — Judge prompts and context

- **Files:** [radioshaq/prompts/judges/task_completion.md](radioshaq/prompts/judges/task_completion.md), [radioshaq/prompts/judges/subtask_quality.md](radioshaq/prompts/judges/subtask_quality.md), [radioshaq/radioshaq/orchestrator/judge.py](radioshaq/radioshaq/orchestrator/judge.py)
- **Tasks:**
  1. **Task Judge:** Ensure the task completion prompt mentions that “completed_tasks” may include results from both agents and tool executions (if we add tool results to completed_tasks). No schema change required.
  2. **Subtask Judge:** Already returns `success`, `output_quality`, `errors`, `recommendations`, `retry_eligible`. Use as in 3.2. Optionally add one line to the prompt: “Set retry_eligible true only when a transient or clearly fixable error occurred.”
  3. **Optional:** Pass `state.context.get("subtask_evaluations")` into the task Judge prompt so it can consider per-task quality when deciding is_complete.

---

### Project 4: Middleware and DELEGATE

**Objective:** Middleware can inject DELEGATE to add tasks; optional use of INJECT_MESSAGE and COMPACT.

#### Activity 4.1 — DELEGATE in default pipeline

- **File:** [radioshaq/radioshaq/orchestrator/factory.py](radioshaq/radioshaq/orchestrator/factory.py)
- **Tasks:**
  1. **Optional middleware that returns DELEGATE:** Add a small “WhitelistDelegate” or “RequestAnalyzer” middleware that, for certain patterns (e.g. “whitelist” in the request), returns `MiddlewareResult(action=MiddlewareAction.DELEGATE, metadata={"agent_name": "whitelist", "task": {...}})`. Register it in `create_middleware_pipeline` so the loop’s `_apply_middleware_result` already appends the task (existing code supports DELEGATE).
  2. **Or:** Rely on the planner in REASONING to emit a whitelist task when the user asks for whitelist; no new middleware required. Prefer this unless product explicitly wants middleware-driven delegation.
- **Subtasks (line-level):**
  - If implementing: in `create_middleware_pipeline`, after TurnLimit and TokenLimit, add a custom middleware that inspects `conv_ctx.messages` or metadata and returns DELEGATE for whitelist-style requests; in `react_loop._apply_middleware_result` the DELEGATE branch already appends to `state.decomposed_tasks`.

#### Activity 4.2 — INJECT_MESSAGE / COMPACT

- **Files:** [radioshaq/radioshaq/vendor/vibe/middleware.py](radioshaq/radioshaq/vendor/vibe/middleware.py), [radioshaq/radioshaq/orchestrator/react_loop.py](radioshaq/radioshaq/orchestrator/react_loop.py)
- **Tasks:**
  1. **No code change** in the loop; `_apply_middleware_result` already handles INJECT_MESSAGE and COMPACT. Add a short comment in the loop that context compaction or injected messages are applied when middleware returns these actions.
  2. **Optional:** Add a “ContextLimit” middleware that returns COMPACT when `conv_ctx.get_token_count()` exceeds a threshold, with metadata indicating how many messages to keep. Implementation can trim `state.context["messages"]` in a follow-up (if the loop reads from that).

---

### Project 5: API and Whitelist Contract

**Objective:** `/messages/process` and `/messages/whitelist-request` work with the unified flow; whitelist response comes from either tools or agent.

#### Activity 5.1 — Process endpoint

- **File:** [radioshaq/radioshaq/api/routes/messages.py](radioshaq/radioshaq/api/routes/messages.py)
- **Tasks:**
  1. **No change** to the handler: it already calls `orchestrator.process_request(request=request_text)` and returns `result.success`, `result.message`, `result.state.task_id`. The unified loop will populate `result.message` from COMMUNICATING.
  2. **Optional:** Return `result.state.phase` or a short summary (e.g. “completed_after_evaluation”) in the response for debugging.

#### Activity 5.2 — Whitelist-request endpoint

- **File:** [radioshaq/radioshaq/api/routes/messages.py](radioshaq/radioshaq/api/routes/messages.py)
- **Tasks:**
  1. **Keep** `message_for_user = result.message` as the primary user-facing message. With the unified loop, when the LLM used the register_callsign tool and replied, `result.message` will be that reply.
  2. **Keep** the loop over `result.state.completed_tasks` for `agent == "whitelist"` to set `approved_from_agent` and optionally override `message_for_user`. So when the flow uses the whitelist agent (ACTING), the response still gets `approved` and `message_for_user` from the task result.
  3. **Document** in the route docstring: “Approved/message can come from either the orchestrator’s final message (tool path) or a completed whitelist agent task (agent path).”

---

### Project 6: Testing and Regression

**Objective:** Unit and integration tests cover the unified path; no regressions on existing behavior.

#### Activity 6.1 — Unit tests: REACT loop

- **File:** [radioshaq/tests/unit/test_orchestrator.py](radioshaq/tests/unit/test_orchestrator.py) (or new file `tests/unit/orchestrator/test_react_loop.py`)
- **Tasks:**
  1. **Test that EVALUATION and ACTING run when tools are set:** Mock `tool_registry` and `llm_client` so REASONING (Stage A) returns a fixed list of 1–2 `DecomposedTask` (e.g. via a mock LLM that returns valid JSON). Assert that the loop proceeds to EVALUATION and then ACTING, and that `state.completed_tasks` is non-empty when the registry returns a mock agent.
  2. **Test that Judge is called:** Mock `judge.evaluate_task_completion` to return `TaskEvaluation(is_complete=True, confidence=0.9, ...)` and assert the loop exits to COMMUNICATING.
  3. **Test subtask judge:** Mock `judge.evaluate_subtask` to return `SubtaskEvaluation(..., retry_eligible=False)` and assert it’s called after an agent run.
  4. **Test COMMUNICATING uses last_llm_reply:** Set `state.context["last_llm_reply"] = "Done"` before COMMUNICATING and assert `state.final_response == "Done"`.

#### Activity 6.2 — Integration / regression

- **Files:** Existing integration tests (e.g. [radioshaq/tests/integration/test_react_field_hq.py](radioshaq/tests/integration/test_react_field_hq.py)), [radioshaq/tests/unit/test_api.py](radioshaq/tests/unit/test_api.py)
- **Tasks:**
  1. **Ensure** `/messages/process` and `/whitelist-request` tests still pass with the unified orchestrator (mock or real LLM/tools as appropriate).
  2. **Add** one integration test that runs a request through the full loop (REASONING → EVALUATION → ACTING → EVALUATION → COMMUNICATING) with mocks and asserts on phase order and final message.

---

## Implementation Order (Recommended)

| Order | Project / Activity | Rationale |
|-------|--------------------|-----------|
| 1 | 1.1 REASONING refactor (plan + optional tools, no short-circuit) | Unblock EVALUATION/ACTING in the same run |
| 2 | 1.3 EVALUATION context (last_evaluation, feed next REASONING) | Judge output drives iteration |
| 3 | 1.4 COMMUNICATING (last_llm_reply, whitelist aggregation) | Correct final message for API and whitelist |
| 4 | 2.1 Decomposition prompt and parser | Stable contract for decomposed_tasks |
| 5 | 1.2 ACTING (subtask judge, optional retry) | Quality and retry in the loop |
| 6 | 3.2 Retry logic for subtask judge | Complete quality loop |
| 7 | 5.x API contract and docs | Clarify whitelist behavior |
| 8 | 6.x Tests | Regression and phase-order coverage |
| 9 | 4.x Middleware (optional DELEGATE/COMPACT) | If product needs middleware-driven delegation |

---

## File-Level Task Summary

| File | Tasks |
|------|--------|
| [radioshaq/radioshaq/orchestrator/react_loop.py](radioshaq/radioshaq/orchestrator/react_loop.py) | REASONING two-stage (plan + tools), no early COMMUNICATING; EVALUATION persist last_evaluation; ACTING subtask judge + retry; COMMUNICATING use last_llm_reply and completed_tasks; add _parse_decomposed_tasks_from_llm |
| [radioshaq/radioshaq/orchestrator/judge.py](radioshaq/radioshaq/orchestrator/judge.py) | Optional: accept subtask_evaluations in task Judge prompt |
| [radioshaq/radioshaq/orchestrator/registry.py](radioshaq/radioshaq/orchestrator/registry.py) | Document agent/capability mapping; optional test |
| [radioshaq/prompts/orchestrator/phases/reasoning.md](radioshaq/prompts/orchestrator/phases/reasoning.md) | Extend output format (capability, payload, tools note) |
| [radioshaq/prompts/judges/subtask_quality.md](radioshaq/prompts/judges/subtask_quality.md) | Optional: one line on retry_eligible |
| [radioshaq/radioshaq/api/routes/messages.py](radioshaq/radioshaq/api/routes/messages.py) | Docstring for whitelist dual path |
| [radioshaq/radioshaq/orchestrator/factory.py](radioshaq/radioshaq/orchestrator/factory.py) | Optional: middleware that returns DELEGATE |
| New or existing test files | Unit tests for phase order, Judge, subtask judge, COMMUNICATING; integration for full loop |

---

## Line-Level Subtask Checklist (react_loop.py)

- **`_phase_reasoning`:**
  - Add “Stage A”: build plan prompt (reasoning.md + context with last_evaluation), call LLM, parse JSON → `state.decomposed_tasks` via `_parse_decomposed_tasks_from_llm`.
  - Add “Stage B”: if tool_registry and llm_client, run tool-calling loop; store last assistant content in `state.context["last_llm_reply"]`; do not set `state.final_response`; do not return early to COMMUNICATING.
  - End of _phase_reasoning: `state.phase = self._next_phase(state.phase)`.
- **`_run_react_loop` (EVALUATION branch):**
  - After `evaluation = await self.judge.evaluate_task_completion(state)`, set `state.context["last_evaluation"] = evaluation` (or dict form).
  - Keep existing branch: if complete and confidence >= 0.7 → COMMUNICATING and break; else next phase.
- **`_phase_acting`:**
  - After each agent execute (and in except): call `await self.judge.evaluate_subtask(...)`; store result; if retry_eligible and under retry cap, set task back to pending or re-append.
- **`_phase_communicating`:**
  - Set `state.final_response = state.context.get("last_llm_reply")` first; then if None, scan completed_tasks for message_for_user/reason; then fallback string.
- **New helper:** `_parse_decomposed_tasks_from_llm(content: str, original_request: str) -> list[DecomposedTask]` with JSON extract and mapping to DecomposedTask; on failure return one task with description=original_request.

---

## Success Criteria

- **Single path:** With tool_registry and llm_client set (current server default), the loop runs REASONING (plan + optional tools) → EVALUATION → ACTING (agents + optional tool tasks) → EVALUATION → … → COMMUNICATING when Judge says done.
- **Judge used:** Task Judge runs in EVALUATION; Subtask Judge runs after each agent run in ACTING.
- **Agents used:** Decomposed tasks with `agent` or capability run via AgentRegistry in ACTING.
- **Whitelist:** Both “LLM + register_callsign tool + final message” and “whitelist agent in completed_tasks” provide the user message and optional approved flag.
- **No regression:** Existing `/process` and `/whitelist-request` behavior preserved or improved; tests pass.
