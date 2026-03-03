# SHAKODS: Comprehensive Planning Document
## Strategic Autonomous Ham Radio and Knowledge Operations Dispatch System

**Version**: 1.0  
**Date**: 2026-02-26  
**Status**: Planning Phase

---

## Executive Summary

SHAKODS is a specialized derivative of nanobot designed for coordinating ham radio operations, managing emergency communications, and facilitating field-to-HQ coordination. It implements a REACT (Reasoning, Evaluation, Acting, Communicating, Tracking) agent orchestrator pattern with specialized judges for task evaluation, JWT-based authentication for distributed operations, and a lightweight serverless AWS deployment model.

### Key Differentiators from nanobot
1. **REACT Orchestrator Pattern** with specialized judges for task evaluation
2. **JWT-based API authentication** instead of MCP tools
3. **Dual-mode architecture**: Field (edge) and HQ (central) coordination
4. **GIS-enabled database** for location-based operations
5. **Ham radio integration** via CAT control, digital modes, and packet radio
6. **Lightweight Lambda deployment** via AWS CLI scripts (no heavy containerization)
7. **Full vendoring** of nanobot/vibe components with Mistral OAuth integration

---

## 1. Architecture Overview

### 1.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SHAKODS SYSTEM                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      ORCHESTRATOR LAYER                                  ││
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐ ││
│  │  │   REACT Loop    │  │  Judge System   │  │   Middleware Pipeline       │ ││
│  │  │                 │  │                 │  │   - Memory upstreaming      │ ││
│  │  │  Reasoning      │  │  - Task Judge   │  │   - Result aggregation      │ ││
│  │  │  Evaluation     │  │  - Subtask Judge│  │   - Context management      │ ││
│  │  │  Acting         │  │  - Quality Gate │  │                             │ ││
│  │  │  Communicating  │  │                 │  │                             │ ││
│  │  │  Tracking       │  │                 │  │                             │ ││
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                        │
│              ┌─────────────────────┼─────────────────────┐                   │
│              ▼                     ▼                     ▼                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │  SPECIALIZED    │  │  SPECIALIZED    │  │  SPECIALIZED                │  │
│  │  AGENTS REGISTRY│  │  AGENTS         │  │  AGENTS                     │  │
│  │                 │  │                 │  │                             │  │
│  │ ┌───────────┐  │  │ ┌───────────┐  │  │ ┌───────────┐  ┌───────────┐ │  │
│  │ │WhatsApp   │  │  │ │Radio TX   │  │  │ │Radio RX   │  │ │GIS/Maps   │ │  │
│  │ │Agent      │  │  │ │Agent      │  │  │ │Agent      │  │ │Agent      │ │  │
│  │ └───────────┘  │  │ └───────────┘  │  │ └───────────┘  │ └───────────┘ │  │
│  │ ┌───────────┐  │  │ ┌───────────┐  │  │ ┌───────────┐  ┌───────────┐ │  │
│  │ │SMS Agent  │  │  │ │Scheduler  │  │  │ │Logging    │  │ │Propagation│ │  │
│  │ │(Twilio)   │  │  │ │Agent      │  │  │ │Agent      │  │ │Agent      │ │  │
│  │ └───────────┘  │  │ └───────────┘  │  │ └───────────┘  │ └───────────┘ │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      DATA LAYER (PostGIS + DynamoDB)                     ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ││
│  │  │Transcripts   │  │GIS Data      │  │Operator      │  │Observability │  ││
│  │  │Store         │  │(lat/long)    │  │Registry      │  │Logs/Traces    │  ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────┐
                    │      DEPLOYMENT MODES           │
                    ├─────────────────────────────────┤
                    │                                 │
                    │  ┌─────────────┐  ┌──────────┐ │
                    │  │ FIELD MODE  │  │ HQ MODE  │ │
                    │  │             │  │          │ │
                    │  │ - Full bot  │  │ - Central│ │
                    │  │ - Propagates│  │ - Receives│ │
                    │  │   to HQ     │  │   fields │ │
                    │  │ - Local LLM │  │ - Coord. │ │
                    │  │   option    │  │          │ │
                    │  └─────────────┘  └──────────┘ │
                    │                                 │
                    └─────────────────────────────────┘
```

### 1.2 Project Structure

```
monorepo/
├── shakods/                          # Main SHAKODS implementation
│   ├── pyproject.toml
│   ├── README.md
│   ├── prompts/                      # All prompts factored out
│   │   ├── orchestrator/
│   │   │   ├── react_system.md
│   │   │   ├── task_judge.md
│   │   │   └── coordinator.md
│   │   ├── specialized/
│   │   │   ├── radio_tx.md
│   │   │   ├── radio_rx.md
│   │   │   ├── whatsapp.md
│   │   │   ├── sms.md
│   │   │   ├── scheduler.md
│   │   │   └── gis.md
│   │   ├── judges/
│   │   │   ├── task_completion.md
│   │   │   ├── quality_assurance.md
│   │   │   └── subtask_evaluator.md
│   │   └── system/
│   │       ├── field_mode.md
│   │       ├── hq_mode.md
│   │       └── subagent.md
│   ├── shakods/                      # Main package
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── cli.py                    # CLI entry point
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   ├── schema.py             # Pydantic config models
│   │   │   └── loader.py             # Config loading
│   │   ├── orchestrator/
│   │   │   ├── __init__.py
│   │   │   ├── react_loop.py         # Main REACT orchestrator
│   │   │   ├── judge.py              # Judge system implementation
│   │   │   ├── planner.py            # Task decomposition
│   │   │   └── registry.py           # Agent registry
│   │   ├── specialized/
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # Base agent class
│   │   │   ├── radio_tx.py           # Radio transmission agent
│   │   │   ├── radio_rx.py           # Radio reception agent
│   │   │   ├── whatsapp_agent.py     # WhatsApp agent
│   │   │   ├── sms_agent.py          # SMS/Twilio agent
│   │   │   ├── scheduler_agent.py    # Call scheduling agent
│   │   │   ├── gis_agent.py          # GIS/maps agent
│   │   │   └── propagation_agent.py  # Field-to-HQ propagation
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── upstream.py           # Memory/results upstreaming
│   │   │   ├── context.py            # Context management
│   │   │   └── pipeline.py           # Middleware pipeline
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── jwt.py                # JWT token handling
│   │   │   ├── oauth_mistral.py      # Mistral OAuth
│   │   │   └── field_auth.py         # Field station auth
│   │   ├── radio/
│   │   │   ├── __init__.py
│   │   │   ├── cat_control.py        # CAT control via hamlib
│   │   │   ├── digital_modes.py      # FLDIGI/WSJTX interface
│   │   │   ├── packet_radio.py       # AX.25/KISS interface
│   │   │   ├── rig_manager.py        # Radio rig management
│   │   │   └── bands.py              # Band/frequency management
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── server.py             # FastAPI server
│   │   │   ├── routes/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── auth.py           # Authentication routes
│   │   │   │   ├── radio.py          # Radio control routes
│   │   │   │   ├── messages.py       # Message routes
│   │   │   │   └── health.py         # Health check routes
│   │   │   └── dependencies.py       # FastAPI dependencies
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── postgres_gis.py       # PostGIS connector
│   │   │   ├── dynamodb.py           # DynamoDB for serverless
│   │   │   ├── models.py             # SQLAlchemy models
│   │   │   ├── transcripts.py        # Transcript storage
│   │   │   └── gis.py                # GIS data management
│   │   ├── channels/
│   │   │   ├── __init__.py
│   │   │   ├── whatsapp.py           # WhatsApp channel
│   │   │   ├── sms.py                # SMS/Twilio channel
│   │   │   └── base.py               # Base channel class
│   │   ├── modes/
│   │   │   ├── __init__.py
│   │   │   ├── field.py              # Field mode implementation
│   │   │   ├── hq.py                 # HQ mode implementation
│   │   │   └── base.py               # Base mode class
│   │   └── vendor/                   # Vendored dependencies
│   │       ├── nanobot/              # Vendored nanobot core
│   │       └── vibe/                 # Vendored vibe components
│   ├── remote_receiver/              # Remote receiver station
│   │   ├── README.md
│   │   ├── pyproject.toml
│   │   ├── receiver/
│   │   │   ├── __init__.py
│   │   │   ├── server.py             # Receiver service
│   │   │   ├── auth.py               # JWT auth for receiver
│   │   │   └── radio_interface.py    # Radio hardware interface
│   │   └── scripts/
│   │       └── deploy_receiver.sh
│   ├── infrastructure/
│   │   ├── aws/
│   │   │   ├── scripts/
│   │   │   │   ├── deploy.sh         # Main deployment script
│   │   │   │   ├── deploy_lambda.sh  # Lambda deployment
│   │   │   │   ├── deploy_db.sh      # Database deployment
│   │   │   │   └── teardown.sh       # Cleanup script
│   │   │   ├── lambda/
│   │   │   │   ├── api_handler.py    # Lambda handler for API
│   │   │   │   ├── message_handler.py  # Lambda handler for messages
│   │   │   │   └── requirements.txt
│   │   │   ├── cloudformation/
│   │   │   │   ├── base.yaml         # Base infrastructure
│   │   │   │   ├── database.yaml     # RDS/PostGIS + DynamoDB
│   │   │   │   ├── api_gateway.yaml  # API Gateway config
│   │   │   │   └── lambda.yaml       # Lambda functions
│   │   │   └── iam/
│   │   │       └── policies.json     # IAM policies
│   │   └── local/
│   │       ├── docker-compose.yml    # Local development
│   │       ├── pm2.config.js         # PM2 configuration
│   │       └── setup.sh              # Local setup script
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_orchestrator/
│       ├── test_radio/
│       ├── test_auth/
│       └── test_api/
├── nanobot-main/                     # Original (reference only)
├── mistral-vibe-main/                # Original (reference only)
└── codex/                            # Original (reference only)
```

---

## 2. Component Specifications

### 2.1 REACT Orchestrator

The REACT (Reasoning, Evaluation, Acting, Communicating, Tracking) orchestrator is the central coordination layer.

**File**: `shakods/shakods/orchestrator/react_loop.py`

**Line-Level Implementation**:
```python
# Lines 1-50: Imports and type definitions
from __future__ import annotations
import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol
from loguru import logger

from shakods.orchestrator.judge import JudgeSystem, TaskEvaluation
from shakods.orchestrator.registry import AgentRegistry
from shakods.middleware.pipeline import MiddlewarePipeline
from shakods.specialized.base import SpecializedAgent

class REACTPhase(Enum):
    REASONING = auto()      # Analyze task, plan approach
    EVALUATION = auto()     # Assess current state against goals
    ACTING = auto()         # Execute actions via specialized agents
    COMMUNICATING = auto()  # Report results, request clarification
    TRACKING = auto()       # Update state, track progress

@dataclass
class REACTState:
    """Current state of the REACT loop."""
    phase: REACTPhase
    task_id: str
    original_request: str
    decomposed_tasks: list[dict[str, Any]]
    completed_tasks: list[dict[str, Any]]
    failed_tasks: list[dict[str, Any]]
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
```

```python
# Lines 51-150: REACTOrchestrator class definition
class REACTOrchestrator:
    """
    REACT (Reasoning, Evaluation, Acting, Communicating, Tracking)
    orchestrator implementing the multi-agent coordination pattern.
    """
    
    def __init__(
        self,
        provider: LLMProvider,
        registry: AgentRegistry,
        judge_system: JudgeSystem,
        middleware: MiddlewarePipeline,
        workspace: Path,
        max_iterations: int = 50,
    ):
        self.provider = provider
        self.registry = registry
        self.judge = judge_system
        self.middleware = middleware
        self.workspace = workspace
        self.max_iterations = max_iterations
        self._states: dict[str, REACTState] = {}
        self._active_tasks: dict[str, asyncio.Task] = {}
```

```python
# Lines 151-300: Core REACT loop implementation
    async def process_request(
        self,
        request: str,
        context: dict[str, Any] | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
    ) -> REACTState:
        """
        Main entry point for processing a request through REACT phases.
        """
        task_id = self._generate_task_id()
        state = REACTState(
            phase=REACTPhase.REASONING,
            task_id=task_id,
            original_request=request,
            decomposed_tasks=[],
            completed_tasks=[],
            failed_tasks=[],
            context=context or {},
        )
        self._states[task_id] = state
        
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            
            # Apply middleware before each phase
            mw_result = await self.middleware.run_before_phase(state)
            if mw_result.should_stop:
                break
            
            # Execute current phase
            if state.phase == REACTPhase.REASONING:
                await self._phase_reasoning(state, on_progress)
            elif state.phase == REACTPhase.EVALUATION:
                await self._phase_evaluation(state, on_progress)
            elif state.phase == REACTPhase.ACTING:
                await self._phase_acting(state, on_progress)
            elif state.phase == REACTPhase.COMMUNICATING:
                await self._phase_communicating(state, on_progress)
            elif state.phase == REACTPhase.TRACKING:
                await self._phase_tracking(state, on_progress)
                
            # Check completion via judge system
            evaluation = await self.judge.evaluate_task_completion(state)
            if evaluation.is_complete:
                state.phase = REACTPhase.COMMUNICATING
                await self._phase_communicating(state, on_progress)
                break
                
            # Transition to next phase
            state.phase = self._next_phase(state.phase)
        
        return state
```

### 2.2 Judge System

The judge system provides evaluation at multiple levels: task completion, subtask quality, and overall coordination.

**File**: `shakods/shakods/orchestrator/judge.py`

**Line-Level Implementation**:
```python
# Lines 1-100: Judge system architecture
@dataclass
class TaskEvaluation:
    """Result of task completion evaluation."""
    is_complete: bool
    confidence: float  # 0.0 to 1.0
    reasoning: str
    missing_elements: list[str]
    quality_score: float  # 0.0 to 1.0
    next_action: str | None = None

@dataclass
class SubtaskEvaluation:
    """Result of subtask execution evaluation."""
    subtask_id: str
    success: bool
    output_quality: float
    errors: list[str]
    recommendations: list[str]
    retry_eligible: bool

class JudgeSystem:
    """
    Multi-level judge system for evaluating task completion.
    """
    
    def __init__(
        self,
        provider: LLMProvider,
        task_judge_prompt: str,
        subtask_judge_prompt: str,
        quality_threshold: float = 0.7,
    ):
        self.provider = provider
        self.task_judge_prompt = task_judge_prompt
        self.subtask_judge_prompt = subtask_judge_prompt
        self.quality_threshold = quality_threshold
```

```python
# Lines 101-200: Task-level judge
    async def evaluate_task_completion(self, state: REACTState) -> TaskEvaluation:
        """
        Orchestrator-level judge: Has the overall task been completed?
        """
        prompt = self._build_task_evaluation_prompt(state)
        
        response = await self.provider.chat(
            messages=[
                {"role": "system", "content": self.task_judge_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        
        # Parse structured evaluation
        evaluation = self._parse_evaluation_response(response.content)
        return evaluation
        
    def _build_task_evaluation_prompt(self, state: REACTState) -> str:
        return f"""
Evaluate task completion for the following state:

Original Request: {state.original_request}

Decomposed Tasks ({len(state.decomposed_tasks)} total):
{self._format_tasks(state.decomposed_tasks)}

Completed Tasks ({len(state.completed_tasks)} total):
{self._format_tasks(state.completed_tasks)}

Failed Tasks ({len(state.failed_tasks)} total):
{self._format_tasks(state.failed_tasks)}

Current Context:
{json.dumps(state.context, indent=2)}

Evaluate: Is the overall request satisfied? What is missing?
Respond with structured JSON including is_complete, confidence, reasoning.
"""
```

### 2.3 Middleware Layer (Memory/Results Upstreaming)

The middleware layer handles propagation of results and memories from subprocesses back to the orchestrator.

**File**: `shakods/shakods/middleware/upstream.py`

**Line-Level Implementation**:
```python
# Lines 1-150: Memory and result upstreaming
@dataclass
class UpstreamEvent:
    """Event to be upstreamed to orchestrator."""
    source: str  # subtask_id, agent_name, etc.
    event_type: str  # "memory", "result", "progress", "error"
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 5  # 1-10, lower = higher priority

class MemoryUpstreamMiddleware:
    """
    Middleware for upstreaming memories and results from specialized agents
    back to the orchestrator's context.
    """
    
    def __init__(
        self,
        memory_store: MemoryStore,
        event_bus: EventBus,
        max_queue_size: int = 1000,
    ):
        self.memory_store = memory_store
        self.event_bus = event_bus
        self._event_queue: asyncio.Queue[UpstreamEvent] = asyncio.Queue(
            maxsize=max_queue_size
        )
        self._subscribed_sources: set[str] = set()
        
    async def subscribe_to_source(self, source_id: str) -> None:
        """Subscribe to upstream events from a specific source."""
        self._subscribed_sources.add(source_id)
        await self.event_bus.subscribe(source_id, self._handle_event)
        
    async def _handle_event(self, event: UpstreamEvent) -> None:
        """Handle incoming upstream event."""
        try:
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Upstream event queue full, dropping event from {event.source}")
            
    async def process_upstream_events(self, context: REACTState) -> None:
        """Process queued upstream events and update orchestrator context."""
        while not self._event_queue.empty():
            event = await self._event_queue.get()
            
            if event.event_type == "memory":
                await self._integrate_memory(event, context)
            elif event.event_type == "result":
                await self._integrate_result(event, context)
            elif event.event_type == "progress":
                await self._update_progress(event, context)
            elif event.event_type == "error":
                await self._handle_error(event, context)
                
    async def _integrate_memory(self, event: UpstreamEvent, context: REACTState) -> None:
        """Integrate upstreamed memory into orchestrator context."""
        memory = event.payload.get("memory")
        if memory:
            # Store in persistent memory
            await self.memory_store.store(
                key=f"upstream:{event.source}:{memory.get('id')}",
                value=memory,
                context=context.task_id,
            )
            # Update ephemeral context
            context.context.setdefault("upstream_memories", []).append(memory)
```

### 2.4 Specialized Agents

#### 2.4.1 Radio Transmission Agent

**File**: `shakods/shakods/specialized/radio_tx.py`

**Line-Level Implementation**:
```python
# Lines 1-100: Radio transmission agent
class RadioTransmissionAgent(SpecializedAgent):
    """
    Specialized agent for ham radio transmission operations.
    Supports voice, digital modes, and packet radio.
    """
    
    name = "radio_tx"
    description = "Transmits messages via ham radio on specified bands and modes"
    capabilities = [
        "voice_transmission",
        "digital_mode_transmission", 
        "packet_radio_transmission",
        "scheduled_transmission",
    ]
    
    def __init__(
        self,
        rig_manager: RigManager,
        digital_modes: DigitalModesInterface,
        packet_radio: PacketRadioInterface,
        config: RadioConfig,
    ):
        self.rig_manager = rig_manager
        self.digital_modes = digital_modes
        self.packet_radio = packet_radio
        self.config = config
        
    async def execute(
        self,
        task: dict[str, Any],
        upstream_callback: Callable[[UpstreamEvent], Awaitable[None]],
    ) -> dict[str, Any]:
        """Execute radio transmission task."""
        transmission_type = task.get("transmission_type")
        frequency = task.get("frequency")
        message = task.get("message")
        mode = task.get("mode", "FM")
        
        # Upstream progress
        await upstream_callback(UpstreamEvent(
            source=self.name,
            event_type="progress",
            payload={"stage": "preparing", "frequency": frequency, "mode": mode},
        ))
        
        if transmission_type == "voice":
            result = await self._transmit_voice(frequency, message, mode)
        elif transmission_type == "digital":
            result = await self._transmit_digital(frequency, message, task.get("digital_mode"))
        elif transmission_type == "packet":
            result = await self._transmit_packet(task.get("destination_callsign"), message)
        else:
            raise ValueError(f"Unknown transmission type: {transmission_type}")
            
        # Upstream result
        await upstream_callback(UpstreamEvent(
            source=self.name,
            event_type="result",
            payload=result,
        ))
        
        return result
```

#### 2.4.2 Radio Reception Agent

**File**: `shakods/shakods/specialized/radio_rx.py`

**Line-Level Implementation**:
```python
# Lines 1-100: Radio reception agent
class RadioReceptionAgent(SpecializedAgent):
    """
    Specialized agent for ham radio reception and monitoring.
    """
    
    name = "radio_rx"
    description = "Monitors and receives messages via ham radio"
    capabilities = [
        "frequency_monitoring",
        "message_reception",
        "signal_reporting",
        "band_scanning",
    ]
    
    async def monitor_frequency(
        self,
        frequency: float,
        duration_seconds: int,
        mode: str = "FM",
        upstream_callback: Callable | None = None,
    ) -> dict[str, Any]:
        """Monitor a frequency for incoming transmissions."""
        
        # Set rig to frequency
        await self.rig_manager.set_frequency(frequency)
        await self.rig_manager.set_mode(mode)
        
        received_messages = []
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < duration_seconds:
            # Check for signals
            signal_detected = await self.rig_manager.check_signal()
            
            if signal_detected and upstream_callback:
                await upstream_callback(UpstreamEvent(
                    source=self.name,
                    event_type="progress",
                    payload={
                        "stage": "signal_detected",
                        "frequency": frequency,
                        "signal_strength": await self.rig_manager.get_signal_strength(),
                    },
                ))
                
            # For digital modes, check for decodable signals
            if mode in ["PSK31", "FT8", "RTTY"]:
                decoded = await self.digital_modes.receive(duration=1)
                if decoded:
                    received_messages.append(decoded)
                    if upstream_callback:
                        await upstream_callback(UpstreamEvent(
                            source=self.name,
                            event_type="result",
                            payload={"message": decoded},
                        ))
                        
        return {
            "frequency": frequency,
            "duration": duration_seconds,
            "messages_received": len(received_messages),
            "messages": received_messages,
        }
```

### 2.5 Ham Radio Interface (CAT Control)

**File**: `shakods/shakods/radio/cat_control.py`

**Line-Level Implementation**:
```python
# Lines 1-150: CAT control via hamlib
import asyncio
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Any
import hamlib  # Python bindings for hamlib

class RigMode(Enum):
    FM = "FM"
    AM = "AM"
    SSB_USB = "USB"
    SSB_LSB = "LSB"
    CW = "CW"
    DIGITAL = "DIG"
    PSK31 = "PSK"
    FT8 = "FT8"

@dataclass
class RigState:
    """Current state of a radio rig."""
    frequency: float  # in Hz
    mode: RigMode
    ptt: bool  # Push-to-talk state
    signal_strength: int  # S-meter reading
    bandwidth: int  # in Hz

class HamlibCATControl:
    """
    CAT (Computer Aided Transceiver) control via hamlib.
    Supports direct hamlib bindings or rigctld daemon.
    """
    
    def __init__(
        self,
        rig_model: int,  # Hamlib rig model number
        port: str,  # Serial port or TCP address
        use_daemon: bool = False,
        daemon_host: str = "localhost",
        daemon_port: int = 4532,
    ):
        self.rig_model = rig_model
        self.port = port
        self.use_daemon = use_daemon
        self.daemon_host = daemon_host
        self.daemon_port = daemon_port
        self._rig = None
        self._lock = asyncio.Lock()
        
    async def connect(self) -> None:
        """Establish connection to radio."""
        if self.use_daemon:
            await self._connect_to_daemon()
        else:
            await self._connect_direct()
            
    async def _connect_direct(self) -> None:
        """Connect directly via hamlib Python bindings."""
        self._rig = hamlib.Rig(self.rig_model)
        self._rig.set_conf("rig_pathname", self.port)
        self._rig.open()
        
    async def set_frequency(self, frequency_hz: float) -> None:
        """Set radio frequency."""
        async with self._lock:
            if self.use_daemon:
                await self._send_daemon_command(f"F {int(frequency_hz)}")
            else:
                self._rig.set_freq(hamlib.RIG_VFO_CURR, int(frequency_hz))
                
    async def set_ptt(self, state: bool) -> None:
        """Set PTT (Push-to-Talk) state."""
        async with self._lock:
            ptt_state = hamlib.RIG_PTT_ON if state else hamlib.RIG_PTT_OFF
            if self.use_daemon:
                cmd = "T 1" if state else "T 0"
                await self._send_daemon_command(cmd)
            else:
                self._rig.set_ptt(hamlib.RIG_VFO_CURR, ptt_state)
                
    async def get_state(self) -> RigState:
        """Get current rig state."""
        async with self._lock:
            if self.use_daemon:
                freq = await self._query_daemon("f")
                mode_str = await self._query_daemon("m")
                ptt_str = await self._query_daemon("t")
                return RigState(
                    frequency=float(freq),
                    mode=RigMode(mode_str.strip()),
                    ptt=ptt_str.strip() == "1",
                    signal_strength=0,  # Would need separate query
                    bandwidth=0,
                )
            else:
                freq = self._rig.get_freq()
                mode = self._rig.get_mode()
                return RigState(
                    frequency=freq,
                    mode=RigMode(mode[0]),  # mode[0] is mode string
                    ptt=False,  # Would need to query
                    signal_strength=0,
                    bandwidth=0,
                )
```

### 2.6 Digital Modes Interface (FLDIGI)

**File**: `shakods/shakods/radio/digital_modes.py`

**Line-Level Implementation**:
```python
# Lines 1-150: FLDIGI digital modes interface
import asyncio
import xmlrpc.client
from dataclasses import dataclass
from typing import Any

@dataclass
class DigitalTransmission:
    """Digital mode transmission configuration."""
    mode: str  # PSK31, RTTY, FT8, etc.
    frequency: float  # Audio frequency in Hz (not RF)
    text: str
    rsid: bool = True  # Transmit RSID for mode identification

class FLDIGIInterface:
    """
    Interface to FLDIGI digital modem software via XML-RPC.
    """
    
    def __init__(self, host: str = "localhost", port: int = 7362):
        self.host = host
        self.port = port
        self._proxy = None
        
    async def connect(self) -> None:
        """Connect to FLDIGI XML-RPC server."""
        self._proxy = xmlrpc.client.ServerProxy(
            f"http://{self.host}:{self.port}/RPC2"
        )
        # Test connection
        await asyncio.to_thread(self._proxy.main.get_version)
        
    async def set_modem(self, mode: str) -> None:
        """Set digital modem mode (PSK31, RTTY, etc.)."""
        await asyncio.to_thread(
            self._proxy.modem.set_by_name, mode
        )
        
    async def transmit_text(self, text: str, delay: float = 0.5) -> None:
        """Transmit text in current digital mode."""
        # Clear TX buffer
        await asyncio.to_thread(self._proxy.text.clear_tx)
        # Add text to buffer
        await asyncio.to_thread(self._proxy.text.add_tx, text)
        # Start transmission
        await asyncio.to_thread(self._proxy.main.tx)
        # Wait for transmission to complete
        while await asyncio.to_thread(self._proxy.main.get_trx_status) == "tx":
            await asyncio.sleep(delay)
        # Return to RX
        await asyncio.to_thread(self._proxy.main.rx)
        
    async def receive_text(self, timeout: float = 10.0) -> str:
        """Receive text from digital mode."""
        start_time = asyncio.get_event_loop().time()
        received = ""
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            # Get RX text
            rx_data = await asyncio.to_thread(self._proxy.text.get_rx)
            if rx_data and rx_data != received:
                received = rx_data
                # Check for end of transmission
                if await asyncio.to_thread(self._proxy.main.get_trx_status) == "rx":
                    break
            await asyncio.sleep(0.1)
            
        return received
```

### 2.7 Packet Radio Interface (AX.25)

**File**: `shakods/shakods/radio/packet_radio.py`

**Line-Level Implementation**:
```python
# Lines 1-150: AX.25 packet radio interface
import asyncio
from dataclasses import dataclass
from typing import Any, Callable
import pyham_ax25  # PyHam AX.25 library

@dataclass
class AX25Frame:
    """AX.25 frame structure."""
    destination: str  # Destination callsign-SSID
    source: str  # Source callsign-SSID
    digipeaters: list[str]  # Digipeater path
    payload: bytes
    pid: int = 0xF0  # Protocol ID

class PacketRadioInterface:
    """
    AX.25 packet radio interface via KISS TNC (Direwolf, SoundModem).
    """
    
    def __init__(
        self,
        callsign: str,
        ssid: int = 0,
        kiss_host: str = "localhost",
        kiss_port: int = 8001,
    ):
        self.callsign = callsign
        self.ssid = ssid
        self.kiss_host = kiss_host
        self.kiss_port = kiss_port
        self._reader = None
        self._writer = None
        self._frame_handlers: list[Callable[[AX25Frame], None]] = []
        
    async def connect(self) -> None:
        """Connect to KISS TNC via TCP."""
        self._reader, self._writer = await asyncio.open_connection(
            self.kiss_host, self.kiss_port
        )
        # Start frame reader task
        asyncio.create_task(self._frame_reader())
        
    async def send_packet(
        self,
        destination: str,
        message: str | bytes,
        digipeaters: list[str] | None = None,
    ) -> None:
        """Send an AX.25 packet."""
        if isinstance(message, str):
            message = message.encode("utf-8")
            
        frame = AX25Frame(
            destination=destination,
            source=f"{self.callsign}-{self.ssid}",
            digipeaters=digipeaters or [],
            payload=message,
        )
        
        # Encode to KISS format
        kiss_frame = self._encode_kiss(frame)
        
        # Send to TNC
        self._writer.write(kiss_frame)
        await self._writer.drain()
        
    def on_frame(self, handler: Callable[[AX25Frame], None]) -> None:
        """Register a handler for received frames."""
        self._frame_handlers.append(handler)
        
    async def _frame_reader(self) -> None:
        """Background task to read frames from TNC."""
        while True:
            try:
                # Read KISS frame from TNC
                kiss_frame = await self._read_kiss_frame()
                if kiss_frame:
                    frame = self._decode_kiss(kiss_frame)
                    # Notify handlers
                    for handler in self._frame_handlers:
                        try:
                            handler(frame)
                        except Exception as e:
                            logger.error(f"Frame handler error: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Frame reader error: {e}")
                await asyncio.sleep(1)
                
    def _encode_kiss(self, frame: AX25Frame) -> bytes:
        """Encode AX.25 frame to KISS format."""
        # Use pyham_ax25 for encoding
        ax25_bytes = pyham_ax25.encode_frame(
            destination=frame.destination,
            source=frame.source,
            digipeaters=frame.digipeaters,
            pid=frame.pid,
            payload=frame.payload,
        )
        # Wrap in KISS format (0xC0 delimiter, 0x00 channel)
        return b"\xC0\x00" + ax25_bytes.replace(b"\xC0", b"\xDB\xDC").replace(b"\xDB", b"\xDB\xDD") + b"\xC0"
```

### 2.8 JWT Authentication System

**File**: `shakods/shakods/auth/jwt.py`

**Line-Level Implementation**:
```python
# Lines 1-150: JWT authentication for distributed agents
from datetime import datetime, timedelta
from typing import Any
import jwt
from pydantic import BaseModel

class JWTConfig(BaseModel):
    """JWT configuration."""
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # Subject (user/agent ID)
    role: str  # Role (field, hq, receiver)
    station_id: str | None = None  # Ham radio callsign
    scopes: list[str]  # Permission scopes
    exp: datetime
    iat: datetime

class JWTAuthManager:
    """
    JWT authentication manager for SHAKODS distributed agents.
    Handles token generation, validation, and refresh.
    """
    
    def __init__(self, config: JWTConfig):
        self.config = config
        
    def create_access_token(
        self,
        subject: str,
        role: str,
        station_id: str | None = None,
        scopes: list[str] | None = None,
    ) -> str:
        """Create a new access token."""
        now = datetime.utcnow()
        expire = now + timedelta(minutes=self.config.access_token_expire_minutes)
        
        payload = TokenPayload(
            sub=subject,
            role=role,
            station_id=station_id,
            scopes=scopes or ["basic"],
            exp=expire,
            iat=now,
        )
        
        return jwt.encode(
            payload.model_dump(),
            self.config.secret_key,
            algorithm=self.config.algorithm,
        )
        
    def verify_token(self, token: str) -> TokenPayload:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
            )
            return TokenPayload(**payload)
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {e}")
            
    def refresh_access_token(self, refresh_token: str) -> str:
        """Create new access token from valid refresh token."""
        payload = self.verify_token(refresh_token)
        
        # Refresh tokens must have 'refresh' scope
        if "refresh" not in payload.scopes:
            raise AuthenticationError("Invalid refresh token")
            
        # Create new access token
        return self.create_access_token(
            subject=payload.sub,
            role=payload.role,
            station_id=payload.station_id,
            scopes=[s for s in payload.scopes if s != "refresh"],
        )
```

### 2.9 PostGIS Database Layer

**File**: `shakods/shakods/database/postgres_gis.py`

**Line-Level Implementation**:
```python
# Lines 1-150: PostGIS database interface
from datetime import datetime
from typing import Any
from geoalchemy2 import Geometry
from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class OperatorLocation(Base):
    """GIS table for operator locations."""
    __tablename__ = "operator_locations"
    
    id = Column(Integer, primary_key=True)
    callsign = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    location = Column(Geometry("POINT", srid=4326))  # WGS 84
    altitude_meters = Column(Float)
    accuracy_meters = Column(Float)
    source = Column(String(50))  # GPS, manual, APRS, etc.
    
class Transcript(Base):
    """Transcript storage with GIS context."""
    __tablename__ = "transcripts"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(100), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    source_callsign = Column(String(20))
    destination_callsign = Column(String(20))
    frequency_hz = Column(Float)
    mode = Column(String(20))
    transcript_text = Column(Text)
    signal_quality = Column(Float)  # 0-1 scale
    location_id = Column(Integer, ForeignKey("operator_locations.id"))
    
class CoordinationEvent(Base):
    """Coordination events between operators."""
    __tablename__ = "coordination_events"
    
    id = Column(Integer, primary_key=True)
    event_type = Column(String(50))  # schedule, connect, relay, etc.
    initiator_callsign = Column(String(20))
    target_callsign = Column(String(20))
    scheduled_time = Column(DateTime)
    frequency_hz = Column(Float)
    mode = Column(String(20))
    status = Column(String(20))  # pending, completed, cancelled
    location = Column(Geometry("POINT", srid=4326))
    
class PostGISManager:
    """
    Manager for PostGIS database operations.
    """
    
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url)
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
        
    async def init_db(self) -> None:
        """Initialize database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
    async def store_operator_location(
        self,
        callsign: str,
        latitude: float,
        longitude: float,
        **kwargs,
    ) -> int:
        """Store operator location with GIS data."""
        async with self.async_session() as session:
            location = OperatorLocation(
                callsign=callsign,
                location=f"SRID=4326;POINT({longitude} {latitude})",
                **kwargs,
            )
            session.add(location)
            await session.commit()
            return location.id
            
    async def find_operators_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float,
    ) -> list[dict[str, Any]]:
        """Find operators within radius of a point."""
        async with self.async_session() as session:
            # Use PostGIS ST_DWithin for efficient radius search
            point = f"SRID=4326;POINT({longitude} {latitude})"
            query = """
                SELECT callsign, timestamp, altitude_meters, source,
                       ST_Distance(location::geography, ST_GeogFromText(:point)) as distance
                FROM operator_locations
                WHERE ST_DWithin(
                    location::geography,
                    ST_GeogFromText(:point),
                    :radius
                )
                AND timestamp > NOW() - INTERVAL '1 hour'
                ORDER BY timestamp DESC
            """
            result = await session.execute(
                query,
                {"point": point, "radius": radius_meters},
            )
            return [dict(row) for row in result]
```

### 2.10 Field Mode Implementation

**File**: `shakods/shakods/modes/field.py`

**Line-Level Implementation**:
```python
# Lines 1-150: Field mode (edge) implementation
import asyncio
from typing import Any

class FieldMode:
    """
    Field mode implementation for edge deployment.
    Runs full SHAKODS locally but propagates to HQ.
    """
    
    def __init__(
        self,
        orchestrator: REACTOrchestrator,
        hq_client: HQClient,
        propagation_config: PropagationConfig,
    ):
        self.orchestrator = orchestrator
        self.hq_client = hq_client
        self.config = propagation_config
        self._pending_propagation: list[dict[str, Any]] = []
        
    async def process_message(
        self,
        message: str,
        source: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Process message locally and propagate to HQ.
        """
        # Process locally through orchestrator
        result = await self.orchestrator.process_request(
            request=message,
            context=context,
        )
        
        # Queue for propagation to HQ
        propagation_packet = {
            "type": "field_operation",
            "source_station": self.config.station_id,
            "timestamp": datetime.utcnow().isoformat(),
            "original_message": message,
            "orchestrator_result": {
                "task_id": result.task_id,
                "completed_tasks": result.completed_tasks,
                "context": result.context,
            },
            "transcripts": await self._get_transcripts(result.task_id),
            "location": await self._get_current_location(),
        }
        
        self._pending_propagation.append(propagation_packet)
        
        # Attempt immediate propagation
        await self._propagate_to_hq()
        
        return {
            "local_result": result,
            "propagated": True,
            "propagation_queue_size": len(self._pending_propagation),
        }
        
    async def _propagate_to_hq(self) -> None:
        """Propagate pending packets to HQ."""
        if not self._pending_propagation:
            return
            
        # Try to send in batch
        try:
            success = await self.hq_client.submit_batch(
                self._pending_propagation
            )
            if success:
                self._pending_propagation.clear()
        except Exception as e:
            logger.error(f"Propagation to HQ failed: {e}")
            # Will retry on next message or scheduled sync
            
    async def run_sync_loop(self) -> None:
        """Background loop for syncing with HQ."""
        while True:
            await asyncio.sleep(self.config.sync_interval_seconds)
            
            if self._pending_propagation:
                await self._propagate_to_hq()
                
            # Also pull any updates from HQ
            try:
                updates = await self.hq_client.get_updates(
                    station_id=self.config.station_id
                )
                for update in updates:
                    await self._apply_hq_update(update)
            except Exception as e:
                logger.error(f"Failed to get updates from HQ: {e}")
```

### 2.11 HQ Mode Implementation

**File**: `shakods/shakods/modes/hq.py`

**Line-Level Implementation**:
```python
# Lines 1-150: HQ mode (central) implementation
from typing import Any
import asyncio

class HQMode:
    """
    HQ mode implementation for central coordination.
    Receives authenticated field connections and coordinates.
    """
    
    def __init__(
        self,
        orchestrator: REACTOrchestrator,
        database: PostGISManager,
        field_registry: FieldStationRegistry,
    ):
        self.orchestrator = orchestrator
        self.database = database
        self.field_registry = field_registry
        self._active_operations: dict[str, dict[str, Any]] = {}
        
    async def receive_field_submission(
        self,
        station_id: str,
        packet: dict[str, Any],
        auth_token: str,
    ) -> dict[str, Any]:
        """
        Receive and process submission from field station.
        """
        # Verify authentication
        if not await self._verify_field_auth(station_id, auth_token):
            raise AuthenticationError(f"Invalid auth for station {station_id}")
            
        # Store in database
        await self._store_field_submission(station_id, packet)
        
        # Determine if HQ orchestration needed
        if self._requires_hq_coordination(packet):
            # Create coordination task
            coordination_task = await self.orchestrator.process_request(
                request=self._build_coordination_request(packet),
                context={
                    "source_station": station_id,
                    "field_packet": packet,
                    "mode": "hq_coordination",
                },
            )
            
            self._active_operations[packet.get("task_id")] = {
                "station_id": station_id,
                "coordination_task": coordination_task,
                "status": "coordinating",
            }
            
            return {
                "received": True,
                "coordination_active": True,
                "coordination_task_id": coordination_task.task_id,
            }
            
        return {"received": True, "coordination_active": False}
        
    async def coordinate_operators(
        self,
        operator_a_callsign: str,
        operator_b_callsign: str,
        purpose: str,
    ) -> dict[str, Any]:
        """
        Coordinate connection between two operators.
        """
        # Get current locations
        loc_a = await self.database.get_latest_location(operator_a_callsign)
        loc_b = await self.database.get_latest_location(operator_b_callsign)
        
        # Determine optimal frequency and mode based on:
        # - Distance between operators
        # - Time of day
        # - Band conditions
        # - Equipment capabilities
        coordination_plan = await self._generate_coordination_plan(
            loc_a, loc_b, purpose
        )
        
        # Send coordination instructions to both operators
        await self._notify_operator(operator_a_callsign, coordination_plan)
        await self._notify_operator(operator_b_callsign, coordination_plan)
        
        # Store coordination event
        await self.database.store_coordination_event(
            event_type="connect",
            initiator_callsign=operator_a_callsign,
            target_callsign=operator_b_callsign,
            scheduled_time=coordination_plan["scheduled_time"],
            frequency_hz=coordination_plan["frequency"],
            mode=coordination_plan["mode"],
            status="pending",
        )
        
        return coordination_plan
```

---

## 3. Prompt Architecture

All prompts are factored into dedicated prompt files under `shakods/prompts/`.

### 3.1 Prompt Organization

```
prompts/
├── orchestrator/
│   ├── react_system.md         # Main REACT orchestrator system prompt
│   ├── task_judge.md           # Task completion judge prompt
│   ├── subtask_judge.md        # Subtask evaluation judge prompt
│   └── coordinator.md          # HQ coordination orchestrator prompt
├── specialized/
│   ├── radio_tx.md             # Radio transmission agent prompt
│   ├── radio_rx.md             # Radio reception agent prompt
│   ├── whatsapp.md             # WhatsApp agent prompt
│   ├── sms.md                  # SMS agent prompt
│   ├── scheduler.md            # Call scheduling agent prompt
│   └── gis.md                  # GIS/maps agent prompt
├── judges/
│   ├── task_completion.md       # Task-level completion criteria
│   ├── quality_assurance.md    # Quality evaluation criteria
│   └── subtask_evaluator.md    # Subtask-specific evaluation
└── system/
    ├── field_mode.md           # Field mode system context
    ├── hq_mode.md              # HQ mode system context
    └── subagent.md             # Subagent system prompt
```

### 3.2 Example Prompt: REACT Orchestrator

**File**: `shakods/prompts/orchestrator/react_system.md`

```markdown
# SHAKODS REACT Orchestrator

You are the central orchestrator for SHAKODS (Strategic Autonomous Ham Radio and Knowledge Operations Dispatch System). Your role is to coordinate specialized agents to complete ham radio operations, emergency communications, and field-to-HQ coordination tasks.

## REACT Loop Phases

You operate in a continuous REACT loop:

1. **REASONING**: Analyze the request, decompose into subtasks, plan approach
2. **EVALUATION**: Assess current state against goals, identify blockers
3. **ACTING**: Delegate to specialized agents, execute actions
4. **COMMUNICATING**: Report progress, request clarification if needed
5. **TRACKING**: Update state, track completion, maintain context

## Available Specialized Agents

- `radio_tx`: Transmits messages via ham radio (voice, digital, packet)
- `radio_rx`: Monitors frequencies, receives messages
- `scheduler`: Schedules calls, manages operator availability
- `gis`: Geographic information, maps, location analysis
- `whatsapp`: WhatsApp message transmission
- `sms`: SMS message transmission via Twilio
- `propagation`: Field-to-HQ data propagation

## Task Decomposition Rules

1. Break complex tasks into discrete, verifiable subtasks
2. Each subtask should have clear success criteria
3. Minimize dependencies between subtasks when possible
4. Identify subtasks that can run in parallel
5. For radio operations, always consider:
   - Band conditions and propagation
   - Operator locations and equipment
   - Regulatory constraints (band privileges, power limits)
   - Emergency priority levels

## Judge System Integration

Your decisions are validated by Judge Agents:
- Task Judge evaluates overall completion
- Subtask Judges evaluate individual agent outputs
- Quality Gates ensure standards before proceeding

When a Judge returns evaluation, respect its assessment and adjust accordingly.

## Communication Protocol

- Report progress after each phase
- Flag blockers immediately
- Request user clarification for ambiguous requests
- Provide structured output for downstream processing

## Emergency Communications Priority

When handling emergency traffic:
1. Priority 1: Life safety (immediate relay)
2. Priority 2: Urgent operational needs
3. Priority 3: Routine coordination

Override normal scheduling for Priority 1.

## Current Context

{{runtime_context}}

## Active Tasks

{{active_tasks}}

## Completed Tasks

{{completed_tasks}}
```

### 3.3 Prompt Loading System

**File**: `shakods/shakods/prompts/loader.py`

```python
# Lines 1-80: Prompt loading system
from enum import StrEnum, auto
from pathlib import Path
from typing import Any
import string

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

class PromptLoader:
    """Load and render prompts from markdown files."""
    
    def __init__(self, prompts_dir: Path | None = None):
        self.prompts_dir = prompts_dir or PROMPTS_DIR
        
    def load(self, path: str, **variables) -> str:
        """
        Load a prompt file and substitute variables.
        
        Args:
            path: Relative path under prompts/ (e.g., "orchestrator/react_system")
            **variables: Template variables to substitute
        """
        file_path = (self.prompts_dir / path).with_suffix(".md")
        
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt not found: {file_path}")
            
        template = file_path.read_text(encoding="utf-8")
        
        # Simple variable substitution
        if variables:
            template = string.Template(template).safe_substitute(variables)
            
        return template
        
    def load_orchestrator_prompt(
        self,
        phase: str,
        context: dict[str, Any],
    ) -> str:
        """Load orchestrator prompt for specific REACT phase."""
        base_prompt = self.load("orchestrator/react_system")
        
        # Add phase-specific guidance
        phase_guidance = self.load(f"orchestrator/phases/{phase}")
        
        return f"{base_prompt}\n\n{phase_guidance}\n\nContext: {context}"
```

---

## 4. AWS Deployment Architecture

### 4.1 Serverless Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                        AWS CLOUD                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   Route 53   │────│ CloudFront   │────│ API Gateway  │       │
│  │   (DNS)      │    │   (CDN)      │    │  (REST/WS)   │       │
│  └──────────────┘    └──────────────┘    └──────┬───────┘       │
│                                                  │               │
│  ┌───────────────────────────────────────────────┼───────────┐  │
│  │                                               ▼           │  │
│  │   ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│  │   │  Lambda    │  │  Lambda    │  │  Lambda    │         │  │
│  │   │  /api/*    │  │  /radio/*  │  │  /messages │         │  │
│  │   │            │  │            │  │            │         │  │
│  │   └─────┬──────┘  └─────┬──────┘  └─────┬──────┘         │  │
│  │         │               │               │                │  │
│  │         └───────────────┼───────────────┘                │  │
│  │                         ▼                                │  │
│  │   ┌─────────────────────────────────────────┐           │  │
│  │   │         Step Functions (Orchestrator)   │           │  │
│  │   │         - REACT state machine           │           │  │
│  │   │         - Judge evaluation flows        │           │  │
│  │   └─────────────────────────────────────────┘           │  │
│  │                         │                              │  │
│  │   ┌─────────────────────┼─────────────────────┐         │  │
│  │   │                     ▼                     │         │  │
│  │   │  ┌──────────┐  ┌──────────┐  ┌──────────┐ │         │  │
│  │   │  │ Lambda   │  │ Lambda   │  │ Lambda   │ │         │  │
│  │   │  │ Judge    │  │ Agent    │  │ Memory   │ │         │  │
│  │   │  │ Tasks    │  │ Workers  │  │ Upstream │ │         │  │
│  │   │  └──────────┘  └──────────┘  └──────────┘ │         │  │
│  │   └─────────────────────────────────────────────┘         │  │
│  │                         │                                 │  │
│  │                         ▼                                 │  │
│  │   ┌─────────────────────────────────────────┐            │  │
│  │   │         EventBridge (Event Bus)         │            │  │
│  │   └─────────────────────────────────────────┘            │  │
│  │                         │                                 │  │
│  └─────────────────────────┼─────────────────────────────────┘  │
│                            ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    DATA LAYER                            │    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │    │
│  │  │ RDS        │  │ DynamoDB   │  │ S3         │        │    │
│  │  │ PostGIS    │  │ Sessions   │  │ Transcripts│        │    │
│  │  │ (GIS data) │  │ States     │  │ Recordings │        │    │
│  │  └────────────┘  └────────────┘  └────────────┘        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              OBSERVABILITY LAYER                         │    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │    │
│  │  │ CloudWatch │  │ X-Ray      │  │ CloudWatch │        │    │
│  │  │ Logs       │  │ Tracing    │  │ Metrics    │        │    │
│  │  └────────────┘  └────────────┘  └────────────┘        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Deployment Scripts

**File**: `shakods/infrastructure/aws/scripts/deploy.sh`

```bash
#!/bin/bash
# Main deployment script for SHAKODS to AWS
# Usage: ./deploy.sh [environment] [region]
# Example: ./deploy.sh production us-east-1

set -e

ENVIRONMENT=${1:-staging}
REGION=${2:-us-east-1}
STACK_NAME="shakods-${ENVIRONMENT}"

echo "🚀 Deploying SHAKODS to ${ENVIRONMENT} in ${REGION}"

# 1. Build Lambda layers
echo "📦 Building Lambda layers..."
./build_layers.sh

# 2. Deploy base infrastructure (VPC, security groups)
echo "🏗️  Deploying base infrastructure..."
aws cloudformation deploy \
    --template-file ../cloudformation/base.yaml \
    --stack-name "${STACK_NAME}-base" \
    --region "${REGION}" \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides Environment="${ENVIRONMENT}"

# 3. Deploy database (RDS PostGIS + DynamoDB)
echo "🗄️  Deploying databases..."
aws cloudformation deploy \
    --template-file ../cloudformation/database.yaml \
    --stack-name "${STACK_NAME}-db" \
    --region "${REGION}" \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        Environment="${ENVIRONMENT}" \
        DBPassword="$(aws secretsmanager get-secret-value --secret-id "shakods/${ENVIRONMENT}/db" --query 'SecretString' --output text | jq -r '.password')"

# 4. Deploy Lambda functions
echo "⚡ Deploying Lambda functions..."
./deploy_lambda.sh "${ENVIRONMENT}" "${REGION}"

# 5. Deploy API Gateway
echo "🌐 Deploying API Gateway..."
aws cloudformation deploy \
    --template-file ../cloudformation/api_gateway.yaml \
    --stack-name "${STACK_NAME}-api" \
    --region "${REGION}" \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides Environment="${ENVIRONMENT}"

# 6. Deploy Step Functions (REACT orchestrator)
echo "🔄 Deploying Step Functions..."
aws stepfunctions create-state-machine \
    --name "${STACK_NAME}-orchestrator" \
    --definition file://../stepfunctions/react_orchestrator.asl.json \
    --role-arn "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):role/${STACK_NAME}-stepfunctions-role" \
    --region "${REGION}" || \
aws stepfunctions update-state-machine \
    --state-machine-arn "arn:aws:states:${REGION}:$(aws sts get-caller-identity --query Account --output text):stateMachine:${STACK_NAME}-orchestrator" \
    --definition file://../stepfunctions/react_orchestrator.asl.json \
    --region "${REGION}"

echo "✅ Deployment complete!"
echo "API Endpoint: $(aws cloudformation describe-stacks --stack-name "${STACK_NAME}-api" --query 'Stacks[0].Outputs[?OutputKey==`ApiEndpoint`].OutputValue' --output text --region "${REGION}")"
```

### 4.3 Lambda Handler

**File**: `shakods/infrastructure/aws/lambda/api_handler.py`

```python
# Lines 1-100: Lambda handler for API requests
import json
import os
from typing import Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext

from shakods.auth.jwt import JWTAuthManager, JWTConfig
from shakods.orchestrator.react_loop import REACTOrchestrator
from shakods.database.dynamodb import DynamoDBStateStore

tracer = Tracer()
logger = Logger()
app = APIGatewayRestResolver()

# Initialize components
jwt_config = JWTConfig(
    secret_key=os.environ["JWT_SECRET"],
    access_token_expire_minutes=int(os.environ.get("JWT_EXPIRE_MINUTES", "30")),
)
auth_manager = JWTAuthManager(jwt_config)
state_store = DynamoDBStateStore(table_name=os.environ["DYNAMODB_TABLE"])
orchestrator = REACTOrchestrator(
    provider=get_provider_from_env(),
    state_store=state_store,
    # ... other config
)

@app.post("/orchestrate")
@tracer.capture_lambda_handler
def orchestrate_request():
    """Main orchestration endpoint."""
    body = app.current_event.json_body or {}
    
    # Verify JWT
    auth_header = app.current_event.get_header_value("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else None
    
    if not token:
        return {"statusCode": 401, "body": json.dumps({"error": "Missing token"})}
        
    try:
        payload = auth_manager.verify_token(token)
    except AuthenticationError as e:
        return {"statusCode": 401, "body": json.dumps({"error": str(e)})}
    
    # Process request through orchestrator
    request_text = body.get("request")
    context = {
        "user_id": payload.sub,
        "role": payload.role,
        "station_id": payload.station_id,
        **body.get("context", {}),
    }
    
    # Start Step Functions execution for REACT loop
    execution_arn = start_orchestrator_workflow(
        request=request_text,
        context=context,
    )
    
    return {
        "statusCode": 202,
        "body": json.dumps({
            "execution_arn": execution_arn,
            "status": "started",
        }),
    }

@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
@tracer.capture_lambda_handler
def lambda_handler(event: dict[str, Any], context: LambdaContext) -> dict[str, Any]:
    return app.resolve(event, context)
```

---

## 5. Local Development Setup

### 5.1 PM2 Configuration

**File**: `shakods/infrastructure/local/pm2.config.js`

```javascript
module.exports = {
  apps: [
    {
      name: 'shakods-api',
      script: 'python -m shakods.api.server',
      cwd: '../..',
      instances: 1,
      autorestart: true,
      watch: ['shakods'],
      ignore_watch: ['__pycache__', '*.pyc'],
      env: {
        NODE_ENV: 'development',
        SHAKODS_MODE: 'field',
        DATABASE_URL: 'postgresql://localhost:5432/shakods',
        JWT_SECRET: 'dev-secret',
      },
      log_file: './logs/api.log',
      out_file: './logs/api.out.log',
      error_file: './logs/api.error.log',
    },
    {
      name: 'shakods-bridge',
      script: 'node bridge/dist/index.js',
      cwd: '../..',
      instances: 1,
      autorestart: true,
      env: {
        BRIDGE_PORT: '3001',
      },
      log_file: './logs/bridge.log',
    },
    {
      name: 'shakods-orchestrator',
      script: 'python -m shakods.orchestrator.worker',
      cwd: '../..',
      instances: 2,
      exec_mode: 'cluster',
      autorestart: true,
      env: {
        WORKER_TYPE: 'orchestrator',
      },
    },
  ],
};
```

### 5.2 Local Setup Script

**File**: `shakods/infrastructure/local/setup.sh`

```bash
#!/bin/bash
# Local development setup for SHAKODS

set -e

echo "🔧 Setting up SHAKODS local development environment"

# 1. Check prerequisites
echo "Checking prerequisites..."
python3 --version || (echo "Python 3.11+ required" && exit 1)
npm --version || (echo "npm required for bridge" && exit 1)

# 2. Create virtual environment
echo "Creating Python virtual environment..."
cd ../..
python3 -m venv .venv
source .venv/bin/activate

# 3. Install SHAKODS package
echo "Installing SHAKODS package..."
pip install -e .

# 4. Install bridge dependencies
echo "Setting up WhatsApp bridge..."
cd infrastructure/local
if [ ! -d "bridge" ]; then
    mkdir -p bridge
    cp -r ../../nanobot-main/bridge/* bridge/
    cd bridge && npm install && npm run build
    cd ..
fi

# 5. Setup local PostgreSQL with PostGIS
echo "Setting up local database..."
if command -v docker &> /dev/null; then
    docker-compose up -d postgres
    sleep 5
    docker-compose exec postgres psql -U shakods -d shakods -c "CREATE EXTENSION IF NOT EXISTS postgis;"
else
    echo "⚠️  Docker not found. Please manually setup PostgreSQL with PostGIS extension"
fi

# 6. Create local config
echo "Creating local configuration..."
mkdir -p ~/.shakods
cat > ~/.shakods/config.yaml << EOF
mode: field
station_id: LOCAL-DEV

auth:
  jwt_secret: local-dev-secret-change-in-production
  
database:
  postgres_url: postgresql://shakods:shakods@localhost:5432/shakods
  dynamodb_endpoint: http://localhost:8000

providers:
  mistral:
    api_key: \${MISTRAL_API_KEY}
    
channels:
  whatsapp:
    enabled: false  # Enable after QR scan
    bridge_url: ws://localhost:3001
  
radio:
  enabled: false  # Enable with actual hardware
  rig_model: 1  # Hamlib rig model number
  port: /dev/ttyUSB0
EOF

# 7. Setup PM2
echo "Installing PM2..."
npm install -g pm2

# 8. Create log directories
mkdir -p logs

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Set your Mistral API key: export MISTRAL_API_KEY=your_key"
echo "  2. Start services: pm2 start infrastructure/local/pm2.config.js"
echo "  3. View logs: pm2 logs"
echo "  4. Run CLI: python -m shakods cli"
```

---

## 6. Remote Receiver Station

### 6.1 Receiver Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  REMOTE RECEIVER STATION                     │
│                     (Edge Deployment)                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                 RECEIVER SERVICE                        │ │
│  │                                                         │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │ │
│  │  │ JWT Auth   │  │ Signal     │  │ HQ         │        │ │
│  │  │ Handler    │  │ Processor  │  │ Client     │        │ │
│  │  └────────────┘  └────────────┘  └────────────┘        │ │
│  │                                                         │ │
│  │  ┌─────────────────────────────────────────────────┐   │ │
│  │  │           HARDWARE INTERFACE LAYER               │   │ │
│  │  │                                                  │   │ │
│  │  │  ┌────────────┐  ┌────────────┐  ┌────────────┐ │   │ │
│  │  │  │ RTL-SDR    │  │ Hamlib     │  │ Audio      │ │   │ │
│  │  │  │ (rtlsdr)   │  │ (CAT)      │  │ (ALSA)     │ │   │ │
│  │  │  └────────────┘  └────────────┘  └────────────┘ │   │ │
│  │  │                                                  │   │ │
│  │  │  ┌────────────┐  ┌────────────┐  ┌────────────┐ │   │ │
│  │  │  │ FLDIGI     │  │ Direwolf   │  │ Custom     │ │   │ │
│  │  │  │ (Digital)  │  │ (Packet)   │  │ Hardware   │ │   │ │
│  │  │  └────────────┘  └────────────┘  └────────────┘ │   │ │
│  │  └─────────────────────────────────────────────────┘   │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                 BUFFERS & QUEUES                        │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │ │
│  │  │ Raw IQ     │  │ Decoded    │  │ Upload     │        │ │
│  │  │ Buffer     │  │ Messages   │  │ Queue      │        │ │
│  │  └────────────┘  └────────────┘  └────────────┘        │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Receiver Implementation

**File**: `shakods/remote_receiver/receiver/server.py`

```python
# Lines 1-150: Remote receiver service
import asyncio
from contextlib import asynccontextmanager
from typing import Any
from fastapi import Depends, FastAPI, WebSocket
from fastapi.security import HTTPBearer

from receiver.auth import JWTReceiverAuth
from receiver.radio_interface import SDRInterface, SignalProcessor
from receiver.hq_client import HQClient

security = HTTPBearer()

class ReceiverService:
    """
    Remote receiver station service.
    Receives radio signals and streams to HQ via authenticated connection.
    """
    
    def __init__(
        self,
        station_id: str,
        jwt_auth: JWTReceiverAuth,
        radio_interface: SDRInterface,
        hq_client: HQClient,
    ):
        self.station_id = station_id
        self.jwt_auth = jwt_auth
        self.radio = radio_interface
        self.hq = hq_client
        self._active_streams: dict[str, asyncio.Task] = {}
        
    async def start(self) -> None:
        """Start the receiver service."""
        # Initialize radio hardware
        await self.radio.initialize()
        
        # Connect to HQ
        await self.hq.connect()
        
        # Start background tasks
        asyncio.create_task(self._signal_processor_loop())
        asyncio.create_task(self._upload_queue_processor())
        
    async def stream_frequency(
        self,
        frequency_hz: float,
        duration_seconds: int,
        websocket: WebSocket,
        token: str,
    ) -> None:
        """WebSocket endpoint for streaming received signals."""
        # Verify JWT
        payload = await self.jwt_auth.verify_token(token)
        
        # Accept WebSocket
        await websocket.accept()
        
        stream_id = f"{payload.sub}:{frequency_hz}"
        
        try:
            # Set radio frequency
            await self.radio.set_frequency(frequency_hz)
            
            # Stream signals
            async for signal in self.radio.receive(duration_seconds):
                await websocket.send_json({
                    "type": "signal",
                    "timestamp": signal.timestamp.isoformat(),
                    "signal_strength": signal.strength_db,
                    "decoded": signal.decoded_data,
                })
                
                # Also queue for HQ upload
                await self._queue_for_hq(signal, payload.sub)
                
        except Exception as e:
            await websocket.send_json({"type": "error", "message": str(e)})
        finally:
            await websocket.close()
            
    async def _signal_processor_loop(self) -> None:
        """Background loop for continuous signal processing."""
        while True:
            try:
                # Scan configured frequencies
                for freq_config in self._get_scan_frequencies():
                    signals = await self.radio.scan_frequency(
                        frequency_hz=freq_config["frequency"],
                        bandwidth_hz=freq_config["bandwidth"],
                        duration_seconds=5,
                    )
                    
                    for signal in signals:
                        if signal.is_interesting:
                            await self._queue_for_hq(signal, "autoscan")
                            
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Signal processor error: {e}")
                await asyncio.sleep(5)
                
    async def _queue_for_hq(
        self,
        signal: SignalData,
        operator_id: str,
    ) -> None:
        """Queue signal data for upload to HQ."""
        packet = {
            "station_id": self.station_id,
            "operator_id": operator_id,
            "timestamp": signal.timestamp.isoformat(),
            "frequency_hz": signal.frequency_hz,
            "signal_strength_db": signal.strength_db,
            "raw_data": signal.raw_data.hex() if signal.raw_data else None,
            "decoded_text": signal.decoded_data,
            "mode": signal.mode,
        }
        
        await self.hq.upload_queue.put(packet)

# FastAPI app factory
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    service = ReceiverService.from_env()
    await service.start()
    app.state.service = service
    yield
    # Shutdown
    await service.shutdown()

app = FastAPI(lifespan=lifespan)

@app.websocket("/stream/{frequency_hz}")
async def websocket_stream(websocket: WebSocket, frequency_hz: float):
    """WebSocket endpoint for signal streaming."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return
        
    service: ReceiverService = app.state.service
    await service.stream_frequency(frequency_hz, 3600, websocket, token)
```

---

## 7. Activity and Task Breakdown

### 7.1 Phase 1: Foundation (Weeks 1-2)

| Project | Activity | File-Level Tasks | Line-Level Subtasks |
|---------|----------|------------------|---------------------|
| shakods | Project scaffolding | Create `pyproject.toml`, `README.md`, directory structure | Define deps: fastapi, sqlalchemy, geoalchemy2, pyhamlib, python-jwt, websockets |
| shakods | Vendor nanobot core | Create `shakods/vendor/nanobot/` | Copy core agent loop (lines 1-502 from nanobot/agent/loop.py), tool registry, bus system |
| shakods | Vendor vibe components | Create `shakods/vendor/vibe/` | Copy middleware.py, agent_loop.py patterns, prompt loading system |
| shakods | Prompt infrastructure | Create `prompts/` directory structure | Implement PromptLoader class (lines 1-80), create prompt markdown files |
| shakods | Configuration system | Create `shakods/config/schema.py` | Define Pydantic models: FieldConfig, HQConfig, RadioConfig, DatabaseConfig |

### 7.2 Phase 2: Orchestrator Core (Weeks 3-4)

| Project | Activity | File-Level Tasks | Line-Level Subtasks |
|---------|----------|------------------|---------------------|
| shakods | REACT loop implementation | Create `shakods/orchestrator/react_loop.py` | Implement REACTPhase enum (lines 1-15), REACTState dataclass (lines 17-30), REACTOrchestrator class with process_request method (lines 51-300) |
| shakods | Judge system | Create `shakods/orchestrator/judge.py` | Implement TaskEvaluation dataclass (lines 1-15), JudgeSystem class with evaluate_task_completion (lines 20-100), evaluate_subtask (lines 101-150) |
| shakods | Agent registry | Create `shakods/orchestrator/registry.py` | Implement AgentRegistry class with register_agent, get_agent_for_task, list_capabilities methods |
| shakods | Middleware pipeline | Create `shakods/middleware/upstream.py` | Implement MemoryUpstreamMiddleware with _integrate_memory, _integrate_result methods (lines 60-100) |
| shakods | Prompt engineering | Write all prompt files | Write react_system.md (100 lines), task_judge.md (50 lines), radio_tx.md (50 lines), radio_rx.md (50 lines) |

### 7.3 Phase 3: Radio Interface (Weeks 5-6)

| Project | Activity | File-Level Tasks | Line-Level Subtasks |
|---------|----------|------------------|---------------------|
| shakods | CAT control | Create `shakods/radio/cat_control.py` | Implement HamlibCATControl class with connect (lines 30-50), set_frequency (lines 51-60), set_ptt (lines 61-75), get_state (lines 76-100) |
| shakods | Digital modes | Create `shakods/radio/digital_modes.py` | Implement FLDIGIInterface class with connect (lines 25-35), set_modem (lines 37-43), transmit_text (lines 45-60), receive_text (lines 62-80) |
| shakods | Packet radio | Create `shakods/radio/packet_radio.py` | Implement PacketRadioInterface with connect (lines 30-40), send_packet (lines 42-60), _frame_reader (lines 75-100), _encode_kiss (lines 102-120) |
| shakods | Rig manager | Create `shakods/radio/rig_manager.py` | Implement RigManager class for managing multiple radio rigs |
| shakods | Band management | Create `shakods/radio/bands.py` | Define band plans, frequency allocations, mode restrictions |

### 7.4 Phase 4: Specialized Agents (Weeks 7-8)

| Project | Activity | File-Level Tasks | Line-Level Subtasks |
|---------|----------|------------------|---------------------|
| shakods | Base agent class | Create `shakods/specialized/base.py` | Implement SpecializedAgent base class with execute method signature, upstream_callback protocol |
| shakods | Radio TX agent | Create `shakods/specialized/radio_tx.py` | Implement RadioTransmissionAgent with execute method (lines 30-80), _transmit_voice, _transmit_digital, _transmit_packet helpers |
| shakods | Radio RX agent | Create `shakods/specialized/radio_rx.py` | Implement RadioReceptionAgent with monitor_frequency method (lines 20-70) |
| shakods | Scheduler agent | Create `shakods/specialized/scheduler_agent.py` | Implement call scheduling logic, operator availability tracking |
| shakods | GIS agent | Create `shakods/specialized/gis_agent.py` | Implement location analysis, propagation prediction |
| shakods | WhatsApp agent | Adapt from nanobot | Port WhatsApp channel logic to agent pattern |
| shakods | SMS agent | Create `shakods/specialized/sms_agent.py` | Implement Twilio SMS integration |
| shakods | Propagation agent | Create `shakods/specialized/propagation_agent.py` | Implement field-to-HQ data propagation logic |

### 7.5 Phase 5: Authentication & Modes (Weeks 9-10)

| Project | Activity | File-Level Tasks | Line-Level Subtasks |
|---------|----------|------------------|---------------------|
| shakods | JWT auth system | Create `shakods/auth/jwt.py` | Implement JWTAuthManager with create_access_token (lines 20-50), verify_token (lines 51-70), refresh_access_token (lines 71-90) |
| shakods | Mistral OAuth | Create `shakods/auth/oauth_mistral.py` | Implement OAuth flow using oauth-cli-kit pattern from nanobot |
| shakods | Field auth | Create `shakods/auth/field_auth.py` | Implement field station authentication, token exchange |
| shakods | Field mode | Create `shakods/modes/field.py` | Implement FieldMode class with process_message (lines 20-70), _propagate_to_hq (lines 72-100), run_sync_loop (lines 101-150) |
| shakods | HQ mode | Create `shakods/modes/hq.py` | Implement HQMode class with receive_field_submission (lines 20-80), coordinate_operators (lines 81-150) |

### 7.6 Phase 6: Database & API (Weeks 11-12)

| Project | Activity | File-Level Tasks | Line-Level Subtasks |
|---------|----------|------------------|---------------------|
| shakods | PostGIS models | Create `shakods/database/models.py` | Define SQLAlchemy models: OperatorLocation, Transcript, CoordinationEvent with geoalchemy2 Geometry columns |
| shakods | PostGIS manager | Create `shakods/database/postgres_gis.py` | Implement PostGISManager with init_db (lines 20-30), store_operator_location (lines 31-50), find_operators_nearby (lines 51-80) |
| shakods | DynamoDB store | Create `shakods/database/dynamodb.py` | Implement DynamoDBStateStore for serverless deployment |
| shakods | Transcript storage | Create `shakods/database/transcripts.py` | Implement transcript storage, search, retrieval |
| shakods | GIS utilities | Create `shakods/database/gis.py` | Implement GIS calculation utilities, propagation prediction |
| shakods | FastAPI server | Create `shakods/api/server.py` | Create FastAPI app with lifespan management |
| shakods | API routes | Create `shakods/api/routes/*.py` | Implement auth.py, radio.py, messages.py, health.py routes |
| shakods | API dependencies | Create `shakods/api/dependencies.py` | Implement get_current_user, get_db, get_orchestrator dependencies |

### 7.7 Phase 7: Remote Receiver (Week 13)

| Project | Activity | File-Level Tasks | Line-Level Subtasks |
|---------|----------|------------------|---------------------|
| remote_receiver | Project setup | Create `remote_receiver/pyproject.toml`, structure | Define dependencies: fastapi, websockets, pyrtlsdr, numpy |
| remote_receiver | Auth system | Create `remote_receiver/receiver/auth.py` | Implement JWTReceiverAuth with verify_token method |
| remote_receiver | SDR interface | Create `remote_receiver/receiver/radio_interface.py` | Implement SDRInterface with initialize, set_frequency, receive methods |
| remote_receiver | Signal processor | Create `remote_receiver/receiver/signal_processor.py` | Implement signal detection, decoding, filtering |
| remote_receiver | HQ client | Create `remote_receiver/receiver/hq_client.py` | Implement HQClient for authenticated uploads |
| remote_receiver | Server | Create `remote_receiver/receiver/server.py` | Implement ReceiverService class, FastAPI app, WebSocket endpoint |
| remote_receiver | Deploy script | Create `remote_receiver/scripts/deploy_receiver.sh` | Raspberry Pi deployment automation |

### 7.8 Phase 8: AWS Infrastructure (Week 14)

| Project | Activity | File-Level Tasks | Line-Level Subtasks |
|---------|----------|------------------|---------------------|
| infrastructure | Deploy scripts | Create `infrastructure/aws/scripts/*.sh` | Implement deploy.sh (100 lines), deploy_lambda.sh (80 lines), deploy_db.sh (50 lines), teardown.sh (50 lines) |
| infrastructure | Lambda handlers | Create `infrastructure/aws/lambda/*.py` | Implement api_handler.py with orchestrate_request (lines 20-80), message_handler.py |
| infrastructure | CloudFormation | Create `infrastructure/aws/cloudformation/*.yaml` | Write base.yaml (VPC, security groups), database.yaml (RDS, DynamoDB), api_gateway.yaml, lambda.yaml |
| infrastructure | Step Functions | Create `infrastructure/aws/stepfunctions/*.asl.json` | Define REACT orchestrator state machine JSON |
| infrastructure | IAM policies | Create `infrastructure/aws/iam/policies.json` | Define Lambda execution roles, API Gateway permissions |

### 7.9 Phase 9: Local Dev & Testing (Week 15)

| Project | Activity | File-Level Tasks | Line-Level Subtasks |
|---------|----------|------------------|---------------------|
| infrastructure | PM2 config | Create `infrastructure/local/pm2.config.js` | Define 3 app configurations: shakods-api, shakods-bridge, shakods-orchestrator |
| infrastructure | Docker Compose | Create `infrastructure/local/docker-compose.yml` | Define postgres service with PostGIS extension |
| infrastructure | Setup script | Create `infrastructure/local/setup.sh` | Implement full local setup automation (100+ lines) |
| shakods | Test suite | Create `tests/` directory | Implement conftest.py, test_orchestrator/, test_radio/, test_api/ |
| shakods | Integration tests | Create `tests/integration/` | Implement end-to-end tests for REACT loop, field-HQ propagation |

### 7.10 Phase 10: Documentation & Polish (Week 16)

| Project | Activity | File-Level Tasks | Line-Level Subtasks |
|---------|----------|------------------|---------------------|
| shakods | README | Create `shakods/README.md` | Write comprehensive documentation (200+ lines) |
| shakods | API docs | Create `shakods/docs/api.md` | Document all API endpoints |
| shakods | Deployment guide | Create `shakods/docs/deployment.md` | Write AWS and local deployment guides |
| shakods | CLI | Create `shakods/cli.py` | Implement command-line interface for local operation |
| shakods | Examples | Create `examples/` directory | Provide usage examples, configuration samples |

---

## 8. Dependencies and Technology Stack

### 8.1 Core Dependencies

```toml
[project]
name = "shakods"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    # Web framework
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "websockets>=14.0",
    
    # Database
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.30.0",
    "geoalchemy2>=0.16.0",
    "boto3>=1.35.0",  # For DynamoDB
    
    # Authentication
    "pyjwt>=2.9.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.0",
    "oauth-cli-kit>=0.1.3",  # For Mistral OAuth
    
    # Ham radio
    "pyhamlib>=4.6",  # Python bindings for hamlib
    "pyham-ax25>=1.0.2",  # AX.25 packet radio
    "numpy>=2.0.0",  # For signal processing
    
    # LLM/AI
    "mistralai>=1.0.0",
    "litellm>=1.81.5",
    
    # Utilities
    "pydantic>=2.9.0",
    "pydantic-settings>=2.6.0",
    "typer>=0.12.0",
    "loguru>=0.7.0",
    "httpx>=0.27.0",
    "python-multipart>=0.0.12",
    
    # AWS (for Lambda)
    "aws-lambda-powertools>=3.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
    "pre-commit>=4.0.0",
]

lambda = [
    "mangum>=0.19.0",  # ASGI adapter for Lambda
]
```

### 8.2 System Dependencies

- **Hamlib**: `sudo apt-get install libhamlib-dev` (for CAT control)
- **FLDIGI**: Install from repository or build from source
- **Direwolf**: For packet radio operations
- **PostGIS**: PostgreSQL extension for GIS data

---

## 9. Summary

This comprehensive planning document outlines the complete architecture and implementation plan for SHAKODS, including:

1. **REACT Orchestrator Pattern**: Multi-phase reasoning with judge system evaluation
2. **JWT-Based Authentication**: For distributed field-to-HQ coordination
3. **Ham Radio Integration**: CAT control, digital modes (FLDIGI), packet radio (AX.25)
4. **Middleware Layer**: Memory and result upstreaming from subprocesses
5. **Prompt Architecture**: All prompts factored into dedicated markdown files
6. **GIS-Enabled Database**: PostGIS for location-based operations
7. **Dual-Mode Deployment**: Field (edge) and HQ (central) modes
8. **Lightweight AWS Deployment**: Lambda functions via CLI scripts
9. **Remote Receiver Station**: Separate service for distributed radio reception
10. **Full Vendoring**: nanobot and vibe components integrated directly

The 16-week implementation plan provides a structured approach to building this complex system incrementally, with clear file-level and line-level tasks for each component.
