# Plan: Orchestrator-as-Quarterback Whitelist Integration

Structured for agent execution: **Projects** → **Activities** → **File-level tasks** → **Line-level subtasks**.

**Purpose**: Whitelisting grants access to **gated services** (e.g. passing messages between bands, relay, and other restricted features). Users request to be whitelisted; the system evaluates and optionally registers their callsign so they can use those services.

---

## Design decisions

- **Orchestrator at the heart**: The REACT orchestrator is the quarterback. It receives a user’s **whitelist request** (text or audio→ASR) for access to gated services, **uses full LLM tool-calling in REASONING** (or delegates to WhitelistAgent as fallback), and ensures the **response is sent back as audio** (TTS over radio or API).
- **Prospective user flow**: User “pings” (API or radio) and states **why they need access to gated services** (e.g. messaging between bands). The system evaluates the request (approve/deny), then sends **audio back** with a short yes/no and reason.
- **Repository pattern**: All access to the callsign registry (list, register, unregister) goes through a **CallsignRegistryRepository** abstraction. API routes, WhitelistAgent (if kept), and LLM-callable tools use this repository.
- **Full tool calling in REACT**: The **REASONING** phase runs an **LLM tool-calling loop**: the LLM receives the user request plus tool definitions (from ToolRegistry); it may return `tool_calls`; we execute each via `tool_registry.execute()`, append tool results to the conversation, and call the LLM again until it returns a final text response (no more tool_calls). That final text is the orchestrator’s answer (e.g. for TTS). Optionally **ACTING** remains for long-running or hardware-heavy tasks that are invoked as “delegate to agent X” when the LLM or judge decides.
- **Subagents as tools where appropriate**: Some current “agents” are single-step, parameterized operations (GIS queries, schedule_call, send_sms, list/register callsigns). These are **better exposed as tools** so the LLM can call them directly in the tool loop. Hardware/stateful/long-running pieces (radio_tx, radio_rx, radio_rx_audio) stay as **agents**; the LLM invokes them via tools that wrap the agent (e.g. `send_audio_over_radio` already wraps radio_tx). See **Investigation: Subagents as tools** below.

---

## Route index (target)

| Method | Path | Purpose |
|--------|------|--------|
| POST | `/messages/whitelist-request` | **Whitelist entry point.** Body: `text` or `message` (required) or multipart `file` (audio). Optional: `callsign`, `send_audio_back` (default true). Orchestrator evaluates via WhitelistAgent → response sent as audio if `send_audio_back` and radio_tx available. |
| POST | `/messages/process` | (Existing) Generic REACT processing; message like "User requests whitelist: …" routes to WhitelistAgent and returns text (no automatic TTS). |

---

## Trigger activation

- **API trigger**: `POST /messages/whitelist-request` with `text` or `message` (or audio file) always runs the whitelist flow.
- **Voice pipeline trigger** (optional): In `radio_rx_audio`, when a transcript segment contains a configured phrase (e.g. `whitelist` or `I want to be whitelisted`), optionally forward the transcript to the whitelist flow (e.g. call same logic as the route or emit an event that the API/bridge consumes). Config: `whitelist_trigger_phrases: list[str]` and `whitelist_trigger_forward: bool` in AudioConfig or a small WhitelistTrigger config block.

---

## Investigation: Subagents as tools

**Question**: Which subagents are better implemented as **simple tool calls** (LLM calls a function with params; we execute and return result) vs. **specialized agents** (orchestrator delegates a task; agent runs its own logic/LLM/hardware)?

**Criteria**: Prefer **tool** when: single-purpose, stateless, “do X with params” and return; no multi-step reasoning or hardware ownership. Prefer **agent** when: multi-step, stateful, owns hardware or long-running process, or needs its own LLM loop.

| Current agent | What it does | Recommendation | Rationale |
|---------------|--------------|----------------|-----------|
| **radio_tx** | Voice/digital/packet TX; PTT; compliance; TTS | **Keep as agent**. Expose via **tool** `send_audio_over_radio` (already exists). | Hardware, compliance, optional TTS; tool is the right interface for the LLM to “send this text as audio”; agent does the work. |
| **radio_rx** | Monitor frequency, receive messages | **Keep as agent**. Optional tool `get_received_messages` if we expose a single “poll” call. | Async monitoring, duration; not a one-shot “call with params.” |
| **radio_rx_audio** | Voice pipeline: ASR, trigger, confirmation, TTS | **Keep as agent**. | Stateful capture/stream, ASR, optional activation phrase; not tool-sized. |
| **gis** | operators_nearby, get_location, propagation_prediction | **Better as tools**: `operators_nearby`, `get_operator_location`, `propagation_prediction`. | Pure DB/query; each action is one call with clear params and return value. |
| **propagation** | predict (field→HQ), relay_planning | **Better as tools**: e.g. `propagation_predict`, `relay_planning` (or fold into GIS tools). | Thin wrapper over GIS; tool schema is simple (lat/lon, radius, etc.). |
| **scheduler** | schedule_call, list_schedule / get_availability | **Better as tools**: `schedule_call`, `list_scheduled_calls` (or `get_pending_events`). | DB-only; single action per call. |
| **sms** | send, receive (webhook) | **Better as tool**: `send_sms(to, body)`. | Single send action; receive is external webhook. |
| **whatsapp** | send (and future receive) | **Better as tool**: `send_whatsapp(message)` (and optional `receive` later). | Same as SMS for send. |
| **whitelist** (to add) | Evaluate request (LLM), register if approved, return message | **Either**: (1) **Tool** `evaluate_whitelist_request(request_text, callsign?)` that does LLM + register and returns `message_for_user`; or (2) **Agent** for Option A. With full tool loop, (1) is enough: LLM can also call `list_registered_callsigns`, `register_callsign`, `send_audio_over_radio` and compose the flow. | With full tool calling, a single tool that “evaluate and optionally register” keeps the whitelist flow simple; no separate WhitelistAgent required unless we want fallback. |

**Implementation strategy**:

- **Phase 1 (this plan)**: Add **full tool-calling loop in REASONING**; register **whitelist tools** (list, register, send_audio) and optionally **evaluate_whitelist_request**. Keep **WhitelistAgent** as optional fallback when the loop is not used (e.g. legacy path).
- **Phase 2 (follow-up)**: Introduce **GIS tools** (`operators_nearby`, `get_operator_location`, `propagation_prediction`), **scheduler tools** (`schedule_call`, `list_scheduled_calls`), **sms**/ **whatsapp** tools. Agents can remain for backward compatibility; orchestrator’s LLM primarily uses tools. ACTING phase then used only for “delegate to radio_tx / radio_rx / radio_rx_audio” when the task is explicitly long-running or hardware-bound.

---

# PROJECT 1: Callsign registry repository (repository pattern)

**Goal**: Single abstraction over “who is registered”; used by API, agents, and tools. Follows repository pattern: interface + implementation backed by existing PostGISManager.

---

## Activity 1.1: Repository interface and implementation

### File-level task 1.1.1: Define repository protocol and implementation

**File**: `radioshaq/radioshaq/callsign/__init__.py` (new package)

- **Line-level subtasks**:
  - Create package `radioshaq.callsign` with `__init__.py`.
  - Export `CallsignRegistryRepository`, `CallsignRegistryRepositoryImpl` (and optional protocol name).

**File**: `radioshaq/radioshaq/callsign/repository.py` (new file)

- **Line-level subtasks**:
  - Define `CallsignRegistryRepository` (Protocol or ABC): `async def list_registered() -> list[dict]`, `async def register(callsign: str, source: str = "api") -> int`, `async def unregister(callsign: str) -> bool`, `async def is_registered(callsign: str) -> bool`.
  - Implement `CallsignRegistryRepositoryImpl` that takes `db` (PostGISManager-like). Each method delegates to `db.list_registered_callsigns()`, `db.register_callsign()`, etc. Normalize callsigns to upper in register/unregister/is_registered.
  - Add a factory or helper: `def get_callsign_repository(db: Any) -> CallsignRegistryRepository | None` that returns `CallsignRegistryRepositoryImpl(db)` if db has the required methods, else None.

---

## Activity 1.2: Wire repository into app and API

### File-level task 1.2.1: Provide repository in app state

**File**: `radioshaq/radioshaq/api/server.py` (lifespan)

- **Line-level subtasks**:
  - After `app.state.db` is set, set `app.state.callsign_repository = get_callsign_repository(app.state.db)` (or None if no db).
  - Ensure no new dependencies; use optional import from `radioshaq.callsign.repository` if needed.

### File-level task 1.2.2: Optional – use repository in existing callsign routes

**File**: `radioshaq/radioshaq/api/routes/callsigns.py`

- **Line-level subtasks**:
  - Add dependency or request.app.state to get `callsign_repository` when available. If repository is set, call `repository.list_registered()` in GET, `repository.register()` in POST /register, etc., instead of calling db directly. If repository is None, keep current db-based behavior (or 503). This keeps API consistent with repository as single source of truth.

---

# PROJECT 2: WhitelistAgent (specialized agent)

**Goal**: A specialized agent that evaluates a whitelist request (reasoning + registry), decides approve/deny, optionally registers the callsign, and returns a short message for the user (to be sent as audio).

---

## Activity 2.1: WhitelistAgent implementation

### File-level task 2.1.1: Create WhitelistAgent

**File**: `radioshaq/radioshaq/specialized/whitelist_agent.py` (new file)

- **Line-level subtasks**:
  - Define class `WhitelistAgent(SpecializedAgent)` with `name = "whitelist"`, `description = "Evaluates whitelist requests and registers approved callsigns"`, `capabilities = ["whitelist", "whitelist_evaluation"]` so that `get_agent_for_task` matches when task description contains “whitelist”.
  - Constructor: `__init__(self, repository: CallsignRegistryRepository | None, llm_client: Any, eval_prompt: str | None = None)`. Store repo, LLM, and optional prompt (or load from prompts dir).
  - Implement `async def execute(self, task: dict, upstream_callback=None) -> dict`:
    - Read `task.get("request_text")` or `task.get("description")` or `task.get("message")` as the user’s reason; optionally `task.get("callsign")` if provided.
    - If repository is None, return `{"approved": False, "reason": "Registry not available.", "error": "no_repository"}`.
    - Build LLM prompt: system = eval prompt (e.g. “You evaluate whitelist requests. Reply with JSON: approved (bool), reason (str), callsign (str if identifiable).”); user = request text. Call LLM once.
    - Parse LLM response (JSON or fallback): extract approved, reason, callsign (if present).
    - If approved and callsign is present and valid, call `await repository.register(callsign, source="whitelist")`. On failure, set reason to indicate registration failed.
    - Return `{"approved": bool, "reason": str, "callsign_registered": str | None, "message_for_user": str}`. `message_for_user` is a short sentence to speak (e.g. “You’re approved and registered as K5ABC.” or “Not approved. Reason: …”).
  - Handle parse/LLM errors: return approved=False and a safe reason/message_for_user.

### File-level task 2.1.2: Whitelist evaluation prompt

**File**: `radioshaq/prompts/specialized/whitelist_evaluate.md` (new file) or inline in agent

- **Line-level subtasks**:
  - Add a short system prompt instructing the LLM to output JSON: `approved`, `reason`, `callsign` (if the user stated their callsign). Emphasize: keep reason and message_for_user brief (one or two sentences) for TTS.

---

## Activity 2.2: Register WhitelistAgent in orchestrator

### File-level task 2.2.1: Create and register WhitelistAgent in factory

**File**: `radioshaq/radioshaq/orchestrator/factory.py`

- **Line-level subtasks**:
  - Import `WhitelistAgent` and `get_callsign_repository` (or repository type).
  - In `create_agent_registry(config, db)`, after existing agents: get `callsign_repo = get_callsign_repository(db)`; build LLM client (reuse same pattern as judge: `_llm_model_string`, `_llm_api_key`, `LLMClient`); optionally load whitelist eval prompt from prompt_loader or use default string.
  - Instantiate `WhitelistAgent(repository=callsign_repo, llm_client=llm_client, eval_prompt=...)` and `registry.register_agent(whitelist_agent)`.
  - Ensure capability `"whitelist"` or `"whitelist_evaluation"` is in the agent so that a task with description “User requests whitelist: …” matches in `get_agent_for_task` (keyword match on “whitelist”).

---

# PROJECT 3: Whitelist tools (ToolRegistry)

**Goal**: Expose list_registered_callsigns and register_callsign as tools (nanobot Tool protocol) so they are available for the orchestrator or future tool-calling loop. send_audio_over_radio already exists.

---

## Activity 3.1: Implement tools using repository

### File-level task 3.1.1: ListRegisteredCallsignsTool

**File**: `radioshaq/radioshaq/specialized/whitelist_tools.py` (new file)

- **Line-level subtasks**:
  - Define class `ListRegisteredCallsignsTool` implementing Tool protocol: `name = "list_registered_callsigns"`, `description` = “List all currently registered (whitelisted) callsigns.”.
  - Constructor: `__init__(self, repository: CallsignRegistryRepository | None)`.
  - `to_schema()`: function with no required parameters (or optional limit).
  - `validate_params()`: return [] (no params) or validate optional params.
  - `async def execute(self) -> str`: if repository is None return “Error: Registry not available.”; else `registered = await self.repository.list_registered()`; return JSON string or human-readable list of callsigns.

### File-level task 3.1.2: RegisterCallsignTool

**File**: `radioshaq/radioshaq/specialized/whitelist_tools.py`

- **Line-level subtasks**:
  - Define class `RegisterCallsignTool` with `name = "register_callsign"`, description = “Register a callsign on the whitelist so they are accepted for messaging.”
  - Parameters in schema: `callsign` (string, required), `source` (string, default “api”).
  - `validate_params()`: require callsign, 3–7 alphanumeric + optional -digit (reuse same pattern as API).
  - `async def execute(self, callsign: str, source: str = "api") -> str`: if repository is None return error; else call `await self.repository.register(callsign.strip().upper(), source)`; return “Registered &lt;callsign&gt;” or error message.

### File-level task 3.1.3: Register tools in create_tool_registry

**File**: `radioshaq/radioshaq/orchestrator/factory.py`

- **Line-level subtasks**:
  - In `create_tool_registry(config, db)`, after registering SendAudioOverRadioTool: get `callsign_repo = get_callsign_repository(db)`; register `ListRegisteredCallsignsTool(callsign_repo)` and `RegisterCallsignTool(callsign_repo)`.
  - Import from `radioshaq.specialized.whitelist_tools`.

---

# PROJECT 4: Whitelist entry point and orchestrator flow

**Goal**: New route `POST /messages/whitelist-request` that accepts text or audio, runs orchestrator (so WhitelistAgent is invoked), and sends the response back as audio. Orchestrator is the quarterback.

---

## Activity 4.1: Whitelist request route

### File-level task 4.1.1: POST /messages/whitelist-request

**File**: `radioshaq/radioshaq/api/routes/messages.py`

- **Line-level subtasks**:
  - Add route `@router.post("/whitelist-request")` with dependencies: get_current_user, get_orchestrator, get_radio_tx_agent (optional), get_config.
  - Accept two shapes: (1) JSON body `{ "text" | "message": str, "callsign": str | null, "send_audio_back": bool }`, or (2) multipart: `file: UploadFile` (audio), form fields `callsign`, `send_audio_back` (default True). If file is provided, run ASR (e.g. transcribe_audio_voxtral) in thread, use transcript as request text.
  - Normalize request text: `request_text = body.get("text") or body.get("message") or transcript`. If empty, raise 400.
  - Build orchestrator input: e.g. `"User requests to be whitelisted. Their message: " + request_text`. If callsign provided, append “ Stated callsign: &lt;callsign&gt;.”
  - Call `result = await orchestrator.process_request(request=orchestrator_input)`.
  - From `result.state.completed_tasks`, find the task result from the whitelist agent (e.g. task.agent == "whitelist" or by inspecting result structure). Extract `message_for_user` or `reason` or fall back to `result.message`.
  - If `send_audio_back` is True and radio_tx agent is available, build task `{"transmission_type": "voice", "message": message_for_user, "use_tts": True}` and `await radio_tx.execute(task)`.
  - Return JSON: `{"success": result.success, "message": message_for_user, "task_id": result.state.task_id, "approved": approved_from_agent_result, "audio_sent": bool}`.

### File-level task 4.1.2: Ensure COMMUNICATING phase uses agent result

**File**: `radioshaq/radioshaq/orchestrator/react_loop.py`

- **Line-level subtasks**:
  - In `_phase_communicating`, if there is exactly one completed task and that task has a result with `message_for_user` or `reason`, set `state.final_response` to that value instead of the generic “Processed: …”. So the route can use `result.message` as the message to speak.
  - Alternatively: set `state.final_response` from the last completed task’s `result.get("message_for_user")` or `result.get("reason")` when present.

---

## Activity 4.2: Optional voice pipeline trigger

### File-level task 4.2.1: Config for whitelist trigger

**File**: `radioshaq/radioshaq/config/schema.py`

- **Line-level subtasks**:
  - In `AudioConfig`, add `whitelist_trigger_phrases: list[str] = Field(default_factory=lambda: ["whitelist", "whitelisted", "want to be whitelisted"])` and `whitelist_trigger_forward: bool = Field(default=False)`.

### File-level task 4.2.2: Forward transcript to whitelist flow from voice pipeline

**File**: `radioshaq/radioshaq/specialized/radio_rx_audio.py`

- **Line-level subtasks**:
  - In `_on_segment_ready`, after trigger_filter.check and before creating pending response: if `whitelist_trigger_forward` and any of `whitelist_trigger_phrases` is in transcript.lower(), call a callback or fire-and-forget to the whitelist flow (e.g. inject into message_bus or call an async helper that POSTs to internal whitelist-request or calls orchestrator). Pass transcript (and optional frequency/mode). Do not block the rest of the pipeline; optional: set a “whitelist_handled” flag so we don’t also do normal response. Implementation detail: if app has no direct access to orchestrator from the agent, use a small “whitelist_request_callback” injected into the agent or use message_bus to push a whitelist request event that a consumer turns into a whitelist-request call.

---

# PROJECT 5: Orchestrator wiring and tool availability

**Goal**: Ensure the orchestrator has access to the tool registry for future tool-calling; ensure WhitelistAgent is used when the request is about whitelist; response is always suitable for TTS.

---

## Activity 5.1: Orchestrator has tool registry reference

### File-level task 5.1.1: Pass tool_registry into orchestrator

**File**: `radioshaq/radioshaq/api/server.py` (lifespan)

- **Line-level subtasks**:
  - After creating orchestrator, set `orchestrator.tool_registry = app.state.tool_registry` (or pass tool_registry into create_orchestrator if the factory is updated to accept it). So the orchestrator can use tools in a future phase (e.g. ACTING with tool execution).

**File**: `radioshaq/radioshaq/orchestrator/factory.py`

- **Line-level subtasks**:
  - Optionally add parameter `tool_registry: ToolRegistry | None = None` to `create_orchestrator` and set `orchestrator.tool_registry = tool_registry` on the created instance so the quarterback has tools available for future use.

---

## Activity 5.2: Final response from WhitelistAgent used for TTS

### File-level task 5.2.1: REACTState context or final_response from completed task

**File**: `radioshaq/radioshaq/orchestrator/react_loop.py`

- **Line-level subtasks**:
  - In `_phase_communicating`, iterate `state.completed_tasks`; if any task has `task.result` with key `message_for_user`, set `state.final_response = task.result["message_for_user"]` and break. If none, keep current generic final_response.
  - Ensure `result.message` in the API response is this final_response so the route can send it as TTS.

---

# PROJECT 6: Full tool calling in REACT

**Goal**: The REASONING phase runs an **LLM tool-calling loop**: the orchestrator’s LLM receives the user request and a list of tools (from ToolRegistry); when the LLM returns `tool_calls`, we execute each via `tool_registry.execute()`, append tool results to the conversation, and call the LLM again until it returns a final text response (no more tool_calls). That text becomes the orchestrator’s answer (e.g. for TTS or for COMMUNICATING). This enables whitelist and other flows to be driven entirely by tools (list_registered_callsigns, register_callsign, send_audio_over_radio, and optionally evaluate_whitelist_request) without requiring a separate WhitelistAgent for the happy path.

---

## Activity 6.1: LLM client support for tool calls

### File-level task 6.1.1: Add chat_with_tools and handle tool_calls in response

**File**: `radioshaq/radioshaq/llm/client.py`

- **Line-level subtasks**:
  - Add a method `async def chat_with_tools(self, messages: list[dict], tools: list[dict], *, temperature=None, max_tokens=None) -> ChatResponseWithTools` (or extend `ChatResponse` with `tool_calls: list`, `content: str`). Use LiteLLM’s `tools` and `tool_choice` (e.g. `"auto"`) in `litellm.acompletion(...)`.
  - In the response, read `choice.message.tool_calls` (and `choice.message.content`). Define a small dataclass or typed dict for one tool call: `id`, `name`, `arguments` (JSON str).
  - Return both `content` and `tool_calls` so the caller can loop: if `tool_calls` is non-empty, execute tools, append assistant message (with `tool_calls`) and tool result messages (role `tool`, `tool_call_id`, `content`), then call `chat_with_tools` again with the extended `messages`.
  - Handle parsing errors for `arguments` (JSON); on failure, append a tool result with an error message so the LLM can retry or conclude.

### File-level task 6.1.2: Optional – max_tool_rounds to avoid infinite loops

**File**: `radioshaq/radioshaq/llm/client.py`

- **Line-level subtasks**:
  - Add parameter `max_tool_rounds: int = 10` to `chat_with_tools` or to the orchestrator’s tool loop. When the number of consecutive tool-call rounds exceeds this, stop and use the last `content` (or a fallback message) as the final response.

---

## Activity 6.2: REASONING phase as LLM tool-calling loop

### File-level task 6.2.1: Run tool loop in REASONING when tool_registry is available

**File**: `radioshaq/radioshaq/orchestrator/react_loop.py`

- **Line-level subtasks**:
  - In `REACTOrchestrator.__init__`, accept optional `tool_registry` and `llm_client` (or get from config). Store them so `_phase_reasoning` can use them.
  - In `_phase_reasoning`: If `self.tool_registry` and `self.llm_client` are set, build initial messages: system (from prompt_loader or fixed “You are the orchestrator. Use tools to fulfill the user request. When done, reply with a short final message for the user.”), user = `state.original_request`. Get tool definitions: `tool_definitions = self.tool_registry.get_definitions()` (or equivalent from nanobot ToolRegistry).
  - Loop (with `max_tool_rounds`): call `await self.llm_client.chat_with_tools(messages, tools=tool_definitions)`. If response has no `tool_calls` (or empty), set `state.final_response = response.content or state.final_response` and store `state.context["llm_messages"] = messages`; then advance phase and exit REASONING.
  - If response has `tool_calls`: for each tool call, parse `arguments` (JSON) into a dict, then `result = await self.tool_registry.execute(name, arguments_dict)`. Append to `messages`: (1) the assistant message with `content` (optional) and `tool_calls` in OpenAI/LiteLLM shape (`id`, `type: "function"`, `function: { name, arguments }`); (2) one message per tool result: `role: "tool"`, `tool_call_id`, `content: str(result)`. Then call the LLM again with the updated messages. If `max_tool_rounds` exceeded, set `state.final_response` from last content or “Tool limit reached.” and exit.
  - Tool definitions from `tool_registry.get_definitions()` are in OpenAI function-calling format; LiteLLM accepts this format for the `tools` argument.
  - If `tool_registry` or `llm_client` is not set, keep current behavior: set a single decomposed task from `state.original_request` and advance phase (so ACTING can still run agent delegation).

### File-level task 6.2.2: Use tool-loop result in COMMUNICATING and route

**File**: `radioshaq/radioshaq/orchestrator/react_loop.py`

- **Line-level subtasks**:
  - In `_phase_communicating`: If `state.final_response` is already set (e.g. from REASONING tool loop), leave it as is. Otherwise, keep existing logic (e.g. set from completed_tasks’ `message_for_user` or generic “Processed: …”). This ensures the whitelist route gets the LLM’s final message when the tool loop completed in REASONING.
  - Optionally: after the tool loop, skip EVALUATION and go straight to COMMUNICATING when `state.final_response` is set (or run a light evaluation so the judge can still STOP/COMPACT).

---

## Activity 6.3: Wire LLM client and tool registry into orchestrator

### File-level task 6.3.1: Create orchestrator with tool_registry and llm_client

**File**: `radioshaq/radioshaq/orchestrator/factory.py`

- **Line-level subtasks**:
  - In `create_orchestrator`, add parameters `tool_registry` and `llm_client` (or build LLM client inside factory from config). Set `orchestrator.tool_registry = tool_registry` and `orchestrator.llm_client = llm_client` on the created `REACTOrchestrator` instance.
  - Ensure `create_orchestrator` is called with the same `tool_registry` built by `create_tool_registry` and an LLM client (e.g. same model as judge).

**File**: `radioshaq/radioshaq/api/server.py` (lifespan)

- **Line-level subtasks**:
  - When creating the orchestrator, pass `app.state.tool_registry` and an LLM client (from config or existing judge’s client) into `create_orchestrator` so the REASONING phase can run the tool loop.

---

## Activity 6.4: Optional – Evaluate-whitelist as a single tool

**Goal**: Allow the whitelist flow to be implemented purely by tools: LLM calls `evaluate_whitelist_request(request_text, callsign?)` and gets back `{ approved, reason, message_for_user, callsign_registered }`; then LLM can call `register_callsign` if needed and `send_audio_over_radio(message_for_user)`. Alternatively, one tool does “evaluate + register + return message” so the LLM only needs to call that tool and then send_audio_over_radio.

### File-level task 6.4.1: EvaluateWhitelistRequestTool (optional)

**File**: `radioshaq/radioshaq/specialized/whitelist_tools.py`

- **Line-level subtasks**:
  - Add class `EvaluateWhitelistRequestTool` implementing Tool protocol: `name = "evaluate_whitelist_request"`, description = “Evaluate a whitelist request: approve or deny, optionally register the callsign, return a short message for the user (for TTS).”
  - Parameters: `request_text` (required), `callsign` (optional). Execute: call same logic as WhitelistAgent (LLM eval + optional register); return JSON string with `approved`, `reason`, `message_for_user`, `callsign_registered`. This allows the REASONING tool loop to handle whitelist without delegating to WhitelistAgent.
  - Register in `create_tool_registry` alongside ListRegisteredCallsignsTool and RegisterCallsignTool.

---

# Execution order (recommended)

1. **Project 1**: Repository (callsign package + repository.py, app state, optionally use in callsign routes).
2. **Project 2**: WhitelistAgent (whitelist_agent.py, prompt, register in create_agent_registry) – optional if using tool-only flow.
3. **Project 3**: Whitelist tools (whitelist_tools.py, register in create_tool_registry).
4. **Project 6**: Full tool calling in REACT (LLM client chat_with_tools, REASONING tool loop, wire tool_registry + llm_client into orchestrator). Enables whitelist via tools.
5. **Project 4**: Route and COMMUNICATING (POST /whitelist-request, _phase_communicating uses final_response from tool loop or task message_for_user).
6. **Project 5**: Orchestrator tool_registry and llm_client in factory/lifespan; final response behavior.
7. **Optional**: Activity 4.2 (voice pipeline trigger) after 4.1 is stable. **Optional**: Activity 6.4 EvaluateWhitelistRequestTool.

---

# Checklist summary

- [ ] **1.1.1** callsign package: repository protocol + CallsignRegistryRepositoryImpl + get_callsign_repository.
- [ ] **1.2.1** server lifespan: app.state.callsign_repository. **1.2.2** (optional) callsign routes use repository.
- [ ] **2.1.1** WhitelistAgent: execute() with repo + LLM, return message_for_user. **2.1.2** whitelist_evaluate prompt.
- [ ] **2.2.1** create_agent_registry registers WhitelistAgent with whitelist capability.
- [ ] **3.1.1** ListRegisteredCallsignsTool. **3.1.2** RegisterCallsignTool. **3.1.3** create_tool_registry registers both.
- [ ] **6.1.1** LLM client: chat_with_tools, return content + tool_calls. **6.1.2** (optional) max_tool_rounds.
- [ ] **6.2.1** REASONING: when tool_registry + llm_client set, run tool loop; set state.final_response from last LLM content. **6.2.2** COMMUNICATING uses final_response when set.
- [ ] **6.3.1** create_orchestrator accepts tool_registry + llm_client; server passes them in lifespan.
- [ ] **6.4.1** (optional) EvaluateWhitelistRequestTool in whitelist_tools.py and register in create_tool_registry.
- [ ] **4.1.1** POST /messages/whitelist-request (text or audio → orchestrator → audio back). **4.1.2** _phase_communicating sets final_response from task result message_for_user when not set by tool loop.
- [ ] **4.2.1** Config whitelist_trigger_phrases, whitelist_trigger_forward. **4.2.2** radio_rx_audio forwards to whitelist when trigger matches (optional).
- [ ] **5.1.1** orchestrator.tool_registry and llm_client set in lifespan/factory. **5.2.1** final_response from completed task message_for_user when applicable.
