# About RadioShaq

RadioShaq is an **autonomous AI agent** for ham radio operations, emergency communications, and field-to-headquarters coordination. The name stands for **S**trategic **H**am **R**adio **A**utonomous **Q**uery and **K**ontrol System. It acts as a single “brain” that understands natural language requests, plans steps, delegates to specialized sub-agents and tools, and decides when a task is done—so operators can interact by voice or text instead of memorizing rig commands or API calls.

This page describes what the agent is, how it thinks and acts, what it can do, and where it runs.

---

## What problem it solves

In the field, operators need to send messages over the air, relay traffic between bands, look up propagation or locations, and manage who is allowed to use the system—often under time pressure. Doing all of this manually means switching between rig controls, mapping software, and written procedures. RadioShaq turns high-level requests (“relay this to 2 m” or “register callsign ABC”) into a sequence of actions: it chooses the right radio agent, calls the right tools (e.g. send audio, register callsign), and uses an internal “judge” to decide when the job is complete. You talk to one system; it coordinates the rest.

---

## How the agent works: the REACT loop

The core of RadioShaq is a **REACT** orchestration loop: **R**easoning → **E**valuation → **A**cting → **C**ommunicating → **T**racking.

1. **Reasoning** — The orchestrator reads the user’s request and, with the help of a large language model (LLM), produces a **plan**: a list of subtasks, each assigned to an agent or tool (e.g. “send this audio via radio_tx”, “check whitelist”). The plan is decomposed into concrete steps the system can execute.

2. **Evaluation** — A **Task Judge** (another LLM call) evaluates whether the overall task is complete. It looks at what has been done, what’s missing, and whether the quality is sufficient. If not, the loop can continue with more actions.

3. **Acting** — Each subtask is dispatched to the right **specialized agent** (e.g. radio TX, SMS, whitelist) or to an **LLM-callable tool** (e.g. send audio over radio, register callsign). Agents and tools perform real operations: keying the rig, sending an SMS, updating the callsign registry, or querying propagation.

4. **Communicating** — Results and context are fed back into the conversation. The orchestrator may issue further LLM calls (e.g. tool use) or advance to the next phase.

5. **Tracking** — State is updated: which subtasks are pending, in progress, or completed; what the judge said; and what to do next. Middleware can enforce turn limits and token budgets so the loop doesn’t run indefinitely.

The loop repeats until the judge says the task is complete, middleware stops it, or a maximum iteration count is reached. The final answer is returned to the user (and optionally propagated to HQ when running in field mode).

---

## Specialized agents

RadioShaq routes work to **specialized agents** registered in an agent registry. Each agent has a **name**, a **description**, and **capabilities** (e.g. `voice_transmission`, `frequency_monitoring`). The orchestrator matches subtasks to agents by explicit name, by required capability, or by keyword in the task description.

| Agent | Role |
|-------|------|
| **radio_tx** | Voice, digital, and packet transmission. Uses CAT (Hamlib) for rig control, optional FLDIGI for digital modes, KISS for packet, and optional HackRF for SDR TX. Respects band plans and compliance (audit log, restricted bands). |
| **radio_rx** | Reception and monitoring. Can report frequency, mode, and signal info from the rig. |
| **RadioAudioReceptionAgent** (voice_rx) | End-to-end voice pipeline: capture audio from the rig, VAD, ASR (speech-to-text), trigger/phrase filtering, and optional response (listen-only, confirm-first, or auto-respond). Only registered when `radio.audio_input_enabled` and audio config are set. |
| **whitelist** | Callsign whitelist and registration. Evaluates requests (with an optional LLM) and updates the callsign repository (PostgreSQL or in-memory). Used for “who can use this station” and relay gating. |
| **sms** | Send SMS via Twilio (when Twilio client and from-number are configured). |
| **whatsapp** | WhatsApp integration (client can be None if not configured). |
| **gis_agent** | Geographic queries (e.g. distance, bearing) using PostGIS when a database is available. |
| **propagation_agent** | Propagation-related queries; uses the GIS agent for location context. |
| **scheduler_agent** | Scheduling and time-based logic; uses the database when available. |

Agents are created at startup from configuration (e.g. rig enabled/disabled, FLDIGI, packet, SDR TX, Twilio). If a dependency is missing (e.g. no rig, no DB), the corresponding agent may be absent or operate in a degraded way.

---

## LLM-callable tools

Besides agents, the orchestrator can call **tools** during the REACT loop (when a tool registry and LLM client are provided). These are invoked by the LLM as part of reasoning (e.g. “use the send_audio tool on 40 m”). Registered tools include:

- **send_audio_over_radio** — Send audio (file or TTS) on a specified band/mode, subject to band allowlist and compliance. Uses the same radio stack as the radio_tx agent (CAT, optional SDR TX).
- **relay_message_between_bands** — Relay a message from one band to another (e.g. 40m → 2m). The message is stored; the recipient polls for it via `GET /transcripts?callsign=<their_callsign>&destination_only=true&band=<target_band>`. Optional site config can enable inject or TX on the target band.
- **list_registered_callsigns** — Return the list of registered callsigns from the callsign repository.
- **register_callsign** — Register a callsign (and optional metadata) in the repository for whitelist/relay gating.

Tools give the LLM direct control over radio and whitelist actions without going through a separate “agent execute” step for every call.

---

## Operational modes

RadioShaq can run in three **modes**, set by configuration (`mode: field | hq | receiver`):

- **Field** — The typical edge deployment. The API and REACT orchestrator run on a field machine (laptop or Raspberry Pi). You process messages locally; optionally, results can be synced to an HQ server (e.g. for central logging or coordination). Field config includes `station_id`, `hq_base_url`, and sync/offline options.

- **HQ** — Central coordination. The server listens for connections from field stations, can run the API and WebSocket for dashboards, and may manage field registration and coordination. HQ config includes host/port, WebSocket settings, and field-station limits.

- **Receiver** — Listen-only. Intended for a remote receiver (e.g. RTL-SDR on a Pi) that streams audio or data to HQ or a field station. The main RadioShaq app is usually run as **field** or **hq**; the “receiver” role is often implemented by a separate service (e.g. `radioshaq.remote_receiver`) forwards SDR data to HQ via `POST /receiver/upload` (same JWT auth). Run with `radioshaq run-receiver`.

So: you **set up** one or more field stations (and optionally an HQ and remote receivers), **configure** database, LLM, radio, and audio, then **operate** by sending messages to the API (e.g. `POST /messages/process`) or by using the voice pipeline (when enabled) so the agent can hear and respond over the air.

---

## Where it runs

- **Main application** — A single process (e.g. `uv run python -m radioshaq.api.server`) runs the FastAPI app, lifespan creates the orchestrator, agent registry, and tool registry. Optional: a MessageBus inbound consumer runs in the background when `RADIOSHAQ_BUS_CONSUMER_ENABLED=1`, so external systems can push messages into the REACT loop.

- **Field station** — Same app, `mode: field`, with a rig (or rig daemon), optional FLDIGI/packet/SDR, and optional voice_rx pipeline. Can run on a laptop or SBC.

- **HQ** — Same app, `mode: hq`, often without a physical rig; used for aggregation and coordination.

- **Remote receiver** — Run `radioshaq run-receiver` (same package); SDR data is sent to the main app or HQ via `POST /receiver/upload`.

---

## Capabilities at a glance

- **Voice** — Transmit and receive voice via CAT rig (and optional TTS). When `radio.audio_input_enabled` and the voice listener are enabled, rig audio is the default capture path: capture → VAD → ASR → MessageBus → orchestrator (and optional relay). Optionally store voice segments as transcripts (`voice_store_transcript`) for GET /transcripts and relay. Receive path supports listen-only, confirm-first, or auto-respond.
- **Digital modes** — FLDIGI integration for digital modulation when `radio.fldigi_enabled` is true.
- **Packet radio** — KISS TNC for packet when `radio.packet_enabled` is true.
- **SDR TX** — Optional HackRF transmit when `radio.sdr_tx_enabled` is true; band and compliance checks apply.
- **Callsign whitelist** — Static list plus DB-backed registration; optional “registry required” for relay/store.
- **Transcripts, relay, inject** — Store transcripts; relay between bands via the orchestrator tool `relay_message_between_bands` or `POST /messages/relay`. Delivery is poll-based by default (recipient uses `GET /transcripts?callsign=...&destination_only=true&band=...`); optional config can enable inject or TX on the target band. Inject test audio for demos; when multiple bands are monitored, inject is band-accurate.
- **GIS / maps** — Operator location (`POST`/`GET /gis/location`), operators-nearby, and emergency events with location (`GET /gis/emergency-events`). The web UI Map page and map panels (Emergency, Radio, Transcripts, Callsigns) show locations; map provider (OSM vs Google) and API keys are set via front-end env vars — see [Configuration](configuration.md) (Maps / web interface subsection).
- **Compliance** — TX audit log, band allowlist, and region-based restricted bands (e.g. FCC, CEPT) to keep operations within regulations.

---

## CLI

- **CLI reference (brief):** 

  - Auth: `radioshaq token` (then set `RADIOSHAQ_TOKEN`).
  - Send a message to the REACT loop: `radioshaq message process "your text"`. 
  - Whitelist request: `radioshaq message whitelist-request "text"`. 
  - Inject for demo: `radioshaq message inject "text"`. 
  - List transcripts: `radioshaq transcripts list`. 
  - Health: `radioshaq health`. 
  - **Config show:** `radioshaq config show [--section llm|memory|overrides] [--config-dir PATH]` — prints LLM, memory, and per-role overrides from config (API keys redacted).
  - Start API: `radioshaq run-api`.
  - **Launch (dev):** `radioshaq launch docker` (start Postgres), `radioshaq launch docker --hindsight` (Postgres + Hindsight), `radioshaq launch pm2` (Postgres + API via PM2), `radioshaq launch pm2 --hindsight` (same + Hindsight). Same commands on Windows, Linux, and macOS.

---

For hardware connection details (IC-7300, FT-450D, RTL-SDR, etc.), see [Radio Usage](radio-usage.md). For all configuration options and how to set them, see [Configuration](configuration.md).
