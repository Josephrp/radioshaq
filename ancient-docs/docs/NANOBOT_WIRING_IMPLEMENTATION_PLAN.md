# Nanobot Wiring, Integration & Implementation Plan

Complete wiring, integration, compatibility and implementation plan for the SHAKODS orchestrator, specialized agents, and vendored nanobot/vibe components. Includes projects, activities, file-level tasks and line-level subtasks.

**Reference:** `shakods/shakods/vendor/nanobot/` (MessageBus, InboundMessage/OutboundMessage, ToolRegistry) and `shakods/shakods/vendor/vibe/` (ConversationContext, MiddlewarePipeline).

---

## 1. Current State Summary

| Component | Location | Status | Nanobot/Vibe Link |
|-----------|----------|--------|-------------------|
| REACTOrchestrator | `orchestrator/react_loop.py` | Implemented, not wired | None yet |
| AgentRegistry | `orchestrator/registry.py` | Implemented, no agents registered | N/A |
| JudgeSystem | `orchestrator/judge.py` | Implemented, needs LLM | N/A |
| MessageBus | `vendor/nanobot/bus/queue.py` | Implemented, unused | Inbound/Outbound/System queues |
| InboundMessage / OutboundMessage | `vendor/nanobot/bus/events.py` | Implemented, unused | Channel ↔ orchestrator |
| ToolRegistry | `vendor/nanobot/tools/registry.py` | Implemented, no tools registered | LLM function-calling |
| ConversationContext / MiddlewarePipeline | `vendor/vibe/middleware.py` | Implemented, not used in REACT loop | before_phase/after_phase |
| LLMClient | `llm/client.py` | Implements chat(); compatible with JudgeSystem | N/A |
| Specialized agents | `specialized/*.py` | 7 agents; not registered | Execute returns dict |
| SendAudioOverRadioTool | `specialized/radio_tools.py` | Tool protocol; not registered | ToolRegistry |

---

## 2. Compatibility Matrix

| SHAKODS Concept | Nanobot/Vibe Concept | Compatibility | Notes |
|-----------------|----------------------|----------------|-------|
| REACTState.original_request | InboundMessage.content | ✅ | Map inbound → request in bridge |
| REACTState.final_response | OutboundMessage.content | ✅ | Publish outbound after COMMUNICATING |
| SpecializedAgent.execute(task) | Tool.execute(**params) | ⚠️ Different | Agents: task dict, callback. Tools: kwargs → str. Adapter or keep both. |
| AgentRegistry.get_agent_for_task | — | N/A | SHAKODS-only; no nanobot equivalent |
| ToolRegistry.get_definitions() | — | N/A | For future LLM tool-calling loop |
| UpstreamEvent (middleware/upstream.py) | SystemMessage (nanobot bus) | ✅ | Can publish system messages for coordination |
| ConversationContext.messages | REACTState.context | ⚠️ | Vibe context has messages list; REACT has context dict. Bridge in adapter. |

---

## 3. Projects and Activities

### Project A: Core Orchestrator Wiring (API & Modes)

**Goal:** REACTOrchestrator + Judge + AgentRegistry built at startup and available to API and Field/HQ modes.

| Activity | Description |
|----------|-------------|
| A.1 | Create orchestrator factory that builds Judge, PromptLoader, AgentRegistry, REACTOrchestrator from Config |
| A.2 | Register all specialized agents (SMS, WhatsApp, Radio TX/RX, GIS, Propagation, Scheduler) with AgentRegistry in factory |
| A.3 | Wire factory into API server lifespan: set `app.state.orchestrator` and optional `app.state.agent_registry` |
| A.4 | Optional: inject optional MessageBus into factory for future inbound/outbound bridge |

**File-level tasks (Project A):**

| File | Task |
|------|------|
| `shakods/shakods/orchestrator/factory.py` (new) | Implement `create_orchestrator(config, db=None, bus=None)` returning REACTOrchestrator with judge + agent_registry; register all agents with dependencies from config/db. |
| `shakods/shakods/api/server.py` | In lifespan: call factory with app.state.config and app.state.db; set app.state.orchestrator (and optionally app.state.agent_registry). |
| `shakods/shakods/orchestrator/__init__.py` | Export factory symbol if desired. |

**Line-level subtasks (Project A):**

- **factory.py (new file):**
  - L1–L20: Imports: Config, JudgeSystem, REACTOrchestrator, PromptLoader, AgentRegistry, LLMClient, all specialized agents (SMS, WhatsApp, RadioTransmission, RadioReception, GIS, Propagation, Scheduler), path for prompts.
  - L21–L45: `def create_judge(config)` → PromptLoader, load judges/task_completion.md and judges/subtask_quality.md, build LLMClient from config.llm, return JudgeSystem(provider, task_prompt, subtask_prompt).
  - L46–L95: `def create_agent_registry(config, db=None)` → AgentRegistry(); instantiate each agent with config/db (SMS: twilio from config if present; WhatsApp: client placeholder; Radio TX: rig_manager from config.radio; Radio RX: rig_manager; GIS: db; Propagation: GISAgent(db); Scheduler: db). register_agent for each. Return registry.
  - L96–L110: `def create_orchestrator(config, db=None, message_bus=None)` → create_judge(config), create_agent_registry(config, db), PromptLoader(), REACTOrchestrator(judge=..., prompt_loader=..., agent_registry=..., max_iterations=20). Return orchestrator.
  - L111–L120: Optional: accept message_bus and store on orchestrator or pass to a bridge (future).
- **api/server.py:**
  - In lifespan, after setting app.state.db: import create_orchestrator from orchestrator.factory; app.state.orchestrator = create_orchestrator(app.state.config, app.state.db). Optionally app.state.agent_registry = same registry used inside (expose via factory return or attribute).

---

### Project B: MessageBus and Channel Bridge (Nanobot Integration)

**Goal:** Inbound messages (e.g. from Lambda/webhook) become REACT requests; REACT responses become OutboundMessage.

| Activity | Description |
|----------|-------------|
| B.1 | Add bridge: consume InboundMessage from MessageBus → call orchestrator.process_request(message.content) → publish OutboundMessage with final response to same channel/chat_id |
| B.2 | Wire MessageBus into API lifespan (optional singleton) and expose endpoint or worker that runs the consume loop |
| B.3 | Lambda message_handler: build InboundMessage from SQS/API payload, publish to MessageBus (requires bus endpoint or direct invoke to API that publishes) |

**File-level tasks (Project B):**

| File | Task |
|------|------|
| `shakods/shakods/orchestrator/bridge.py` (new) | Implement async loop or one-shot: consume_inbound() → orchestrator.process_request(msg.content) → publish_outbound(OutboundMessage(channel=msg.channel, chat_id=msg.chat_id, content=result.message)). Handle task_id/session in context if needed. |
| `shakods/shakods/api/server.py` | Optional: create MessageBus in lifespan; app.state.message_bus = MessageBus(); pass to create_orchestrator(..., message_bus=app.state.message_bus). |
| `shakods/infrastructure/aws/lambda/message_handler.py` | Parse body to InboundMessage fields (channel, sender_id, chat_id, content); call shared helper that either publishes to MessageBus (if API has bus) or invokes orchestrator directly (e.g. via HTTP to API /messages/process). |

**Line-level subtasks (Project B):**

- **bridge.py (new):**
  - L1–L15: Imports: MessageBus, InboundMessage, OutboundMessage, REACTOrchestrator, loguru.
  - L16–L35: `async def process_inbound_message(bus: MessageBus, orchestrator: REACTOrchestrator, message: InboundMessage)` → result = await orchestrator.process_request(message.content); OutboundMessage(channel=message.channel, chat_id=message.chat_id, content=result.message); await bus.publish_outbound(out). Return result.
  - L36–L55: `async def run_inbound_consumer(bus: MessageBus, orchestrator: REACTOrchestrator)` → while True: msg = await bus.consume_inbound(); await process_inbound_message(bus, orchestrator, msg). Optional: wrap in try/except and log.
- **message_handler.py:**
  - In _process_record: build InboundMessage(channel=body.get("channel","api"), sender_id=body.get("sender_id",""), chat_id=body.get("chat_id",""), content=body.get("content","")); then either (1) POST to HQ URL /internal/bus/inbound with serialized message, or (2) invoke local process_request if running in same process. Document that full bus integration requires API to run consumer.

---

### Project C: ToolRegistry and LLM Tool-Calling Path (Optional/Future)

**Goal:** ToolRegistry populated with SendAudioOverRadioTool (and others); an LLM conversation loop can use get_definitions() and execute() for function calling.

| Activity | Description |
|----------|-------------|
| C.1 | Create tool registry factory: from config build ToolRegistry, register SendAudioOverRadioTool(rig_manager, config), optionally other tools. |
| C.2 | Expose ToolRegistry in app state or orchestrator so a future “LLM runner” (e.g. chat loop with tool calls) can use it. No change to REACT loop required unless we add a REASONING path that uses LLM + tools. |
| C.3 | Compatibility: Keep AgentRegistry for REACT ACTING; ToolRegistry for optional LLM-driven tool use. Bridge: tools can delegate to agents (as SendAudioOverRadioTool already does). |

**File-level tasks (Project C):**

| File | Task |
|------|------|
| `shakods/shakods/orchestrator/factory.py` | Add `def create_tool_registry(config, db=None)` → ToolRegistry(); add SendAudioOverRadioTool(rig_manager from config, config); registry.register(tool); return registry. Optional: create_rig_manager(config.radio) helper. |
| `shakods/shakods/api/server.py` | Optional: app.state.tool_registry = create_tool_registry(config) in lifespan. |
| `shakods/specialized/radio_tools.py` | No change; already implements Tool protocol and delegates to RadioTransmissionAgent. |

**Line-level subtasks (Project C):**

- **factory.py:**
  - In create_tool_registry: L?–L?: Build rig_manager if config.radio.enabled (use existing rig manager if present in codebase, else None). SendAudioOverRadioTool(rig_manager=rig_manager, config=config); tool_registry.register(send_audio_tool); return tool_registry.

---

### Project D: Vibe Middleware Integration with REACT Loop

**Goal:** Run MiddlewarePipeline (TurnLimit, TokenLimit, Upstream) before/after REACT phases where applicable.

| Activity | Description |
|----------|-------------|
| D.1 | Build ConversationContext from REACTState (messages from context or minimal list; stats from new or existing counter; task_id, phase from state). |
| D.2 | In REACTOrchestrator._run_react_loop, before each phase: build context; run pipeline.run_before_phase(context); if result.action != CONTINUE, handle STOP/COMPACT/INJECT/UPSTREAM/DELEGATE. |
| D.3 | After each phase: run pipeline.run_after_phase(context, phase_result); same handling. DELEGATE could map to “push task to decomposed_tasks with agent name”. |
| D.4 | Optional: add default pipeline in factory (TurnLimitMiddleware(max_turns=20), TokenLimitMiddleware(max_tokens=50_000)). |

**File-level tasks (Project D):**

| File | Task |
|------|------|
| `shakods/shakods/orchestrator/react_loop.py` | Add optional middleware_pipeline: MiddlewarePipeline | None to REACTOrchestrator.__init__. In _run_react_loop, at start of loop: build ConversationContext from state (messages=[] or state.context.get("messages",[]), stats=AgentStats(), task_id=state.task_id, phase=state.phase.value). Call run_before_phase; if STOP then break; if COMPACT then trim context; if INJECT then add message to state; if DELEGATE then append task to state.decomposed_tasks. After phase execution call run_after_phase; same handling. |
| `shakods/shakods/orchestrator/factory.py` | Optional: create_middleware_pipeline(config) → pipeline with TurnLimitMiddleware(max_iterations), TokenLimitMiddleware(50_000); return pipeline. Pass to REACTOrchestrator(..., middleware_pipeline=pipeline). |

**Line-level subtasks (Project D):**

- **react_loop.py:**
  - __init__: Add parameter middleware_pipeline: Any = None; self.middleware_pipeline = middleware_pipeline.
  - _run_react_loop, start of while: conv_ctx = ConversationContext(messages=state.context.get("messages", []), stats=AgentStats(), task_id=state.task_id, phase=state.phase.value if hasattr(state.phase, "value") else str(state.phase)); result = await self.middleware_pipeline.run_before_phase(conv_ctx) if self.middleware_pipeline else MiddlewareResult.continue_(); if result.action == MiddlewareAction.STOP: break; elif result.action == MiddlewareAction.DELEGATE: state.decomposed_tasks.append(DecomposedTask(..., agent=result.metadata.get("agent_name"), payload=result.metadata.get("task", {}))); etc.
  - After each phase block: run_after_phase(conv_ctx, phase_result); same action handling.

---

### Project E: Lambda and API Consistency

**Goal:** Lambda handler and API share the same message shape and can both drive orchestrator (direct or via bus).

| Activity | Description |
|----------|-------------|
| E.1 | Define shared message schema (channel, sender_id, chat_id, content, optional media, metadata) matching InboundMessage. |
| E.2 | Lambda: parse body to schema; if HQ URL configured, POST to /messages/process or /internal/bus/inbound; else log and ack. |
| E.3 | API: /messages/process already accepts body.message/body.text; optionally accept channel, chat_id for OutboundMessage routing in future. |

**File-level tasks (Project E):**

| File | Task |
|------|------|
| `shakods/shakods/api/routes/messages.py` | Optional: accept optional channel, chat_id in body; store in state or use when publishing OutboundMessage later. |
| `infrastructure/aws/lambda/message_handler.py` | Use InboundMessage.to_dict() or same schema; document env for HQ_URL; POST to HQ_URL/messages/process with JSON body. |

---

## 4. Implementation Order (Recommended)

1. **Project A** (Core Orchestrator Wiring) — unblocks /messages/process and Field/HQ modes.
2. **Project B** (MessageBus Bridge) — enables channel-agnostic ingest and reply.
3. **Project C** (ToolRegistry) — when LLM tool-calling is needed.
4. **Project D** (Vibe Middleware) — when turn/token limits and delegation from middleware are required.
5. **Project E** (Lambda/API consistency) — in parallel with B.

---

## 5. File-Level Task Checklist

| # | File | Task | Project |
|---|------|------|---------|
| 1 | `shakods/orchestrator/factory.py` | New: create_judge, create_agent_registry, create_orchestrator | A |
| 2 | `shakods/api/server.py` | Lifespan: create_orchestrator(config, db), set app.state.orchestrator | A |
| 3 | `shakods/orchestrator/bridge.py` | New: process_inbound_message, run_inbound_consumer | B |
| 4 | `shakods/api/server.py` | Optional: MessageBus in lifespan, pass to factory/bridge | B |
| 5 | `infrastructure/aws/lambda/message_handler.py` | Build InboundMessage, POST to API or publish bus | B, E |
| 6 | `shakods/orchestrator/factory.py` | create_tool_registry, register SendAudioOverRadioTool | C |
| 7 | `shakods/orchestrator/react_loop.py` | Optional middleware_pipeline in __init__ and _run_react_loop | D |
| 8 | `shakods/orchestrator/factory.py` | create_middleware_pipeline, pass to REACTOrchestrator | D |
| 9 | `shakods/api/routes/messages.py` | Optional body channel, chat_id for outbound routing | E |

---

## 6. Line-Level Subtask Reference (Project A — Factory)

| File | Lines | Subtask |
|------|-------|---------|
| factory.py | 1–20 | Imports: Config, JudgeSystem, REACTOrchestrator, PromptLoader, AgentRegistry, LLMClient, PromptLoader DEFAULT_PROMPTS_DIR, all agents, path |
| factory.py | 21–45 | create_judge(config): loader, task_prompt, subtask_prompt, LLMClient from config.llm, return JudgeSystem(provider, task_prompt, subtask_prompt) |
| factory.py | 46–60 | create_agent_registry start: registry = AgentRegistry(); build LLMClient/model string from config.llm |
| factory.py | 61–75 | Register SMSAgent (twilio_client, from_number from config if present), WhatsAppAgent(client=None), RadioTransmissionAgent(rig_manager, digital_modes, packet_radio, config) |
| factory.py | 76–90 | Register RadioReceptionAgent, GISAgent(db), PropagationAgent(gis_agent), SchedulerAgent(db) |
| factory.py | 91–110 | create_orchestrator(config, db=None, message_bus=None): judge, registry, loader, return REACTOrchestrator(judge=judge, prompt_loader=loader, agent_registry=registry, max_iterations=20) |
| server.py | lifespan | After db init: from shakods.orchestrator.factory import create_orchestrator; app.state.orchestrator = create_orchestrator(app.state.config, app.state.db) |

---

## 7. Dependencies and Rig Manager Note

- **Rig manager:** Radio agents expect a `rig_manager` with set_frequency, set_mode, set_ptt. If not present in codebase, use None and agents return “not configured” (already implemented).
- **Twilio:** SMSAgent expects twilio_client and from_number; config can expose twilio_sid, twilio_token, from_number for factory to build client.
- **DB:** PostGISManager with find_operators_nearby, get_latest_location, store_coordination_event, get_pending_coordination_events used by GIS, Scheduler, Propagation. Factory receives db from server lifespan.

---

---

## 8. Implementation Status (Completed)

| Project | Status | Files Touched |
|---------|--------|----------------|
| **A. Core Orchestrator Wiring** | Done | `orchestrator/factory.py` (new), `api/server.py` (lifespan), `orchestrator/__init__.py` (exports) |
| **B. MessageBus and Bridge** | Done | `orchestrator/bridge.py` (new), `api/server.py` (MessageBus in lifespan), `api/routes/bus.py` (new, POST /internal/bus/inbound), `infrastructure/aws/lambda/message_handler.py` (forward to HQ when SHAKODS_HQ_URL set) |
| **C. ToolRegistry** | Done | `factory.py` create_tool_registry, `api/server.py` app.state.tool_registry |
| **D. Vibe Middleware in REACT** | Done | `react_loop.py` middleware_pipeline; `factory.py` create_middleware_pipeline |
| **E. Lambda/API consistency** | Done | `messages.py` optional channel/chat_id; Lambda uses shared InboundMessage schema |

- **Factory:** `create_orchestrator(config, db=None, message_bus=None)` builds Judge (LLMClient + judge prompts), AgentRegistry (all 7 specialized agents with rig/db/twilio from config), and REACTOrchestrator. API lifespan sets `app.state.orchestrator` and `app.state.message_bus`.
- **Bridge:** `process_inbound_message(bus, orchestrator, message)` and `run_inbound_consumer(bus, orchestrator)` in `orchestrator/bridge.py`. POST `/internal/bus/inbound` publishes to MessageBus; a background consumer can be started separately to run REACT on each inbound message and publish outbound.
- **Lambda:** Set `SHAKODS_HQ_URL`; Lambda POSTs to `{HQ_URL}/internal/bus/inbound` or `/messages/process` (auth). Shared schema: channel, sender_id, chat_id, content (or message/text).
- **Bus consumer:** Set `SHAKODS_BUS_CONSUMER_ENABLED=1` to run inbound consumer in API lifespan.

*End of plan.*
