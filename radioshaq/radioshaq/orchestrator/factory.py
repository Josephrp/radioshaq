"""Orchestrator factory: build REACTOrchestrator with Judge, AgentRegistry, and optional MessageBus."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from radioshaq.compliance_plugin import get_band_plan_source_for_config
from radioshaq.config.resolve import get_llm_config_for_role, get_memory_config_for_role
from radioshaq.config.schema import Config, LLMConfig
from radioshaq.llm.client import LLMClient
from radioshaq.orchestrator.judge import JudgeSystem
from radioshaq.orchestrator.react_loop import REACTOrchestrator
from radioshaq.orchestrator.registry import AgentRegistry
from radioshaq.prompts import PromptLoader
from radioshaq.specialized.gis_agent import GISAgent
from radioshaq.specialized.propagation_agent import PropagationAgent
from radioshaq.specialized.radio_rx import RadioReceptionAgent
from radioshaq.specialized.radio_tx import RadioTransmissionAgent
from radioshaq.specialized.scheduler_agent import SchedulerAgent
from radioshaq.specialized.sms_agent import SMSAgent
from radioshaq.specialized.whatsapp_agent import WhatsAppAgent
from radioshaq.specialized.whitelist_agent import WhitelistAgent
from radioshaq.vendor.nanobot.tools.registry import ToolRegistry
from radioshaq.specialized.radio_tools import SendAudioOverRadioTool
from radioshaq.specialized.whitelist_tools import ListRegisteredCallsignsTool, RegisterCallsignTool
from radioshaq.specialized.memory_tools import RecallMemoryTool, ReflectMemoryTool
from radioshaq.specialized.relay_tools import RelayMessageTool
from radioshaq.specialized.gis_tools import (
    GetOperatorLocationTool,
    OperatorsNearbyTool,
    SetOperatorLocationTool,
)
from radioshaq.callsign import get_callsign_repository


def _prompts_dir() -> Path:
    """Resolve prompts directory (package-relative)."""
    try:
        from radioshaq.prompts import DEFAULT_PROMPTS_DIR as D
        return D
    except Exception:
        # Package layout: .../radioshaq/orchestrator/factory.py -> .../radioshaq/prompts
        return Path(__file__).resolve().parent.parent / "prompts"


def _llm_model_string(config: Config) -> str:
    """Build LiteLLM-style model string from config (uses global llm)."""
    return _llm_model_string_from_llm_config(config.llm)


def _llm_model_string_from_llm_config(llm: LLMConfig) -> str:
    """Build LiteLLM-style model string from an LLMConfig."""
    model = getattr(llm, "model", "mistral-large-latest") or "mistral-large-latest"
    provider = getattr(llm, "provider", None)
    p = str(provider).lower() if provider else ""
    if p == "mistral" and "/" not in model:
        return f"mistral/{model}"
    if p == "openai" and "/" not in model:
        return f"openai/{model}"
    if p == "anthropic" and "/" not in model:
        return f"anthropic/{model}"
    if p == "custom":
        return f"custom/{model}" if "/" not in model else model
    if "/" not in model and not model.startswith(("openai/", "anthropic/", "mistral/", "custom/", "ollama/")):
        return f"mistral/{model}"
    return model


def _llm_api_key(config: Config) -> str | None:
    """Get API key for configured provider (global llm)."""
    return _llm_api_key_from_llm_config(config.llm)


def _llm_api_key_from_llm_config(llm: LLMConfig) -> str | None:
    """Get API key from an LLMConfig."""
    if getattr(llm, "mistral_api_key", None):
        return llm.mistral_api_key
    if getattr(llm, "openai_api_key", None):
        return llm.openai_api_key
    if getattr(llm, "anthropic_api_key", None):
        return llm.anthropic_api_key
    if getattr(llm, "custom_api_key", None):
        return llm.custom_api_key
    return None


def create_judge(config: Config) -> JudgeSystem:
    """Build JudgeSystem with LLM provider and judge prompts."""
    prompts_dir = _prompts_dir()
    loader = PromptLoader(prompts_dir=prompts_dir)
    task_path = "judges/task_completion"
    subtask_path = "judges/subtask_quality"
    try:
        task_prompt = loader.load_raw(task_path)
    except FileNotFoundError:
        task_prompt = "Evaluate if the overall task is complete. Respond with JSON: is_complete, confidence, reasoning, missing_elements, quality_score, next_action."
    try:
        subtask_prompt = loader.load_raw(subtask_path)
    except FileNotFoundError:
        subtask_prompt = "Evaluate subtask execution. Respond with JSON: success, output_quality, errors, recommendations, retry_eligible."

    llm_cfg = get_llm_config_for_role(config, "judge")
    model = _llm_model_string_from_llm_config(llm_cfg)
    api_key = _llm_api_key_from_llm_config(llm_cfg)
    provider = LLMClient(
        model=model,
        api_key=api_key,
        api_base=getattr(llm_cfg, "custom_api_base", None),
        temperature=getattr(llm_cfg, "temperature", 0.1),
        max_tokens=getattr(llm_cfg, "max_tokens", 4096),
    )
    return JudgeSystem(
        provider=provider,
        task_judge_prompt=task_prompt,
        subtask_judge_prompt=subtask_prompt,
        quality_threshold=0.7,
    )


def _create_rig_manager(config: Config) -> Any:
    """Create RigManager and register one rig from config.radio if enabled. Return None if disabled."""
    if not getattr(config.radio, "enabled", False):
        return None
    try:
        from radioshaq.radio import RigManager
        from radioshaq.radio.cat_control import HamlibCATControl
    except ImportError as e:
        logger.warning("Radio stack not available: %s", e)
        return None
    rm = RigManager()
    cat = HamlibCATControl(
        rig_model=getattr(config.radio, "rig_model", 1),
        port=getattr(config.radio, "port", "/dev/ttyUSB0"),
        use_daemon=getattr(config.radio, "use_daemon", False),
        daemon_host=getattr(config.radio, "daemon_host", "localhost"),
        daemon_port=getattr(config.radio, "daemon_port", 4532),
    )
    rm.register_rig("default", cat)
    return rm


def _create_digital_modes(config: Config) -> Any:
    """Create FLDIGI interface if enabled. Return None otherwise."""
    if not getattr(config.radio, "fldigi_enabled", False):
        return None
    try:
        from radioshaq.radio.digital_modes import FLDIGIInterface
        return FLDIGIInterface(
            host=getattr(config.radio, "fldigi_host", "localhost"),
            port=getattr(config.radio, "fldigi_port", 7362),
        )
    except ImportError:
        return None


def _create_packet_radio(config: Config) -> Any:
    """Create packet radio interface if enabled. Return None otherwise."""
    if not getattr(config.radio, "packet_enabled", False):
        return None
    try:
        from radioshaq.radio.packet_radio import PacketRadioInterface
        return PacketRadioInterface(
            callsign=getattr(config.radio, "packet_callsign", "N0CALL"),
            ssid=getattr(config.radio, "packet_ssid", 0),
            kiss_host=getattr(config.radio, "packet_kiss_host", "localhost"),
            kiss_port=getattr(config.radio, "packet_kiss_port", 8001),
        )
    except ImportError:
        return None


def _create_sdr_transmitter(config: Config) -> Any:
    """Create HackRF transmitter if sdr_tx_enabled and backend is hackrf. Return None otherwise."""
    if not getattr(config.radio, "sdr_tx_enabled", False):
        return None
    if getattr(config.radio, "sdr_tx_backend", "hackrf").strip().lower() != "hackrf":
        return None
    try:
        from radioshaq.radio.sdr_tx import HackRFTransmitter
        band_plan = get_band_plan_source_for_config(
            getattr(config.radio, "restricted_bands_region", "FCC"),
            getattr(config.radio, "band_plan_region", None),
        )
        return HackRFTransmitter(
            device_index=getattr(config.radio, "sdr_tx_device_index", 0),
            serial_number=getattr(config.radio, "sdr_tx_serial", None),
            max_gain=getattr(config.radio, "sdr_tx_max_gain", 47),
            allow_bands_only=getattr(config.radio, "sdr_tx_allow_bands_only", True),
            audit_log_path=getattr(config.radio, "tx_audit_log_path", None),
            restricted_region=getattr(config.radio, "restricted_bands_region", "FCC"),
            band_plan_source=band_plan,
        )
    except Exception as e:
        logger.warning("SDR TX (HackRF) not available: %s", e)
        return None


def create_agent_registry(config: Config, db: Any = None, message_bus: Any = None) -> AgentRegistry:
    """Build AgentRegistry and register all specialized agents with config/db dependencies."""
    registry = AgentRegistry()

    rig_manager = _create_rig_manager(config)
    digital_modes = _create_digital_modes(config)
    packet_radio = _create_packet_radio(config)
    sdr_transmitter = _create_sdr_transmitter(config)

    ptt_coordinator = None
    if rig_manager and getattr(config, "audio", None):
        audio_cfg = config.audio
        if getattr(audio_cfg, "ptt_coordination_enabled", True):
            try:
                from radioshaq.radio.ptt_coordinator import PTTCoordinator
                ptt_coordinator = PTTCoordinator(
                    rig_manager=rig_manager,
                    cooldown_ms=getattr(audio_cfg, "ptt_cooldown_ms", 500),
                    break_in_enabled=getattr(audio_cfg, "break_in_enabled", True),
                )
                logger.debug("PTTCoordinator created for half-duplex safety")
            except Exception as e:
                logger.warning("PTTCoordinator not created: %s", e)

    sms_client = None
    sms_from = None
    if getattr(config, "twilio_sid", None) or getattr(config, "twilio_from", None):
        try:
            from twilio.rest import Client
            sid = getattr(config, "twilio_sid", None) or getattr(config, "twilio_account_sid", None)
            token = getattr(config, "twilio_token", None) or getattr(config, "twilio_auth_token", None)
            if sid and token:
                sms_client = Client(sid, token)
                sms_from = getattr(config, "twilio_from", None) or getattr(config, "twilio_from_number", None)
        except ImportError:
            pass

    registry.register_agent(SMSAgent(twilio_client=sms_client, from_number=sms_from))
    registry.register_agent(WhatsAppAgent(client=None))

    registry.register_agent(
        RadioTransmissionAgent(
            rig_manager=rig_manager,
            digital_modes=digital_modes,
            packet_radio=packet_radio,
            config=config,
            sdr_transmitter=sdr_transmitter,
            ptt_coordinator=ptt_coordinator,
        )
    )
    registry.register_agent(
        RadioReceptionAgent(rig_manager=rig_manager, digital_modes=digital_modes)
    )

    if getattr(config.radio, "audio_input_enabled", False) and getattr(config, "audio", None):
        try:
            from radioshaq.audio.stream_processor import AudioStreamProcessor
            from radioshaq.audio.capture import AudioCaptureService
            from radioshaq.specialized.radio_rx_audio import RadioAudioReceptionAgent

            audio_cfg = config.audio
            stream_processor = AudioStreamProcessor(
                sample_rate=audio_cfg.input_sample_rate,
                frame_duration_ms=30,
                vad_aggressiveness={
                    "normal": 0,
                    "low": 1,
                    "aggressive": 2,
                    "very_aggressive": 3,
                }.get(
                    getattr(audio_cfg.vad_mode, "value", str(audio_cfg.vad_mode)), 2
                ),
                pre_speech_buffer_ms=audio_cfg.pre_speech_buffer_ms,
                post_speech_buffer_ms=audio_cfg.post_speech_buffer_ms,
                min_speech_duration_ms=audio_cfg.min_speech_duration_ms,
                max_speech_duration_ms=audio_cfg.max_speech_duration_ms,
                silence_duration_ms=audio_cfg.silence_duration_ms,
                use_rnnoise=(
                    getattr(audio_cfg, "denoising_enabled", True)
                    and getattr(audio_cfg, "denoising_backend", "rnnoise") == "rnnoise"
                ),
            )
            capture_service = AudioCaptureService(
                stream_processor=stream_processor,
                input_device=audio_cfg.input_device,
                sample_rate=audio_cfg.input_sample_rate,
                chunk_duration_ms=30,
            )
            tx_agent = registry.get_agent("radio_tx")
            transcript_storage = None
            if db is not None:
                try:
                    from radioshaq.database.transcripts import TranscriptStorage
                    transcript_storage = TranscriptStorage(db=db)
                except Exception:
                    pass
            rx_audio_agent = RadioAudioReceptionAgent(
                config=audio_cfg,
                rig_manager=rig_manager,
                capture_service=capture_service,
                stream_processor=stream_processor,
                response_agent=tx_agent,
                message_bus=message_bus,
                radio_config=getattr(config, "radio", None),
                transcript_storage=transcript_storage,
            )
            registry.register_agent(rx_audio_agent)
            logger.debug("Registered RadioAudioReceptionAgent (voice_rx)")
        except ImportError as e:
            logger.warning("Voice RX not available (missing voice_rx deps): %s", e)
        except Exception as e:
            logger.warning("Could not register RadioAudioReceptionAgent: %s", e)

    gis_agent = GISAgent(db=db)
    registry.register_agent(gis_agent)
    registry.register_agent(PropagationAgent(gis_agent=gis_agent))
    registry.register_agent(SchedulerAgent(db=db))

    callsign_repo = get_callsign_repository(db)
    whitelist_eval_prompt = None
    try:
        loader = PromptLoader(prompts_dir=_prompts_dir())
        whitelist_eval_prompt = loader.load_raw("specialized/whitelist_evaluate")
    except Exception:
        pass
    # Per-subagent LLM: use agent name as role key (llm_overrides["whitelist"] etc.)
    llm_cfg = get_llm_config_for_role(config, "whitelist")
    llm_client = LLMClient(
        model=_llm_model_string_from_llm_config(llm_cfg),
        api_key=_llm_api_key_from_llm_config(llm_cfg),
        api_base=getattr(llm_cfg, "custom_api_base", None),
        temperature=getattr(llm_cfg, "temperature", 0.1),
        max_tokens=getattr(llm_cfg, "max_tokens", 4096),
    )
    registry.register_agent(
        WhitelistAgent(repository=callsign_repo, llm_client=llm_client, eval_prompt=whitelist_eval_prompt)
    )

    logger.debug("Agent registry created with %d agents", len(registry.list_agents()))
    return registry


def create_tool_registry(config: Config, db: Any = None, *, app: Any = None) -> ToolRegistry:
    """Build ToolRegistry and register LLM-callable tools (e.g. SendAudioOverRadioTool, whitelist, relay)."""
    registry = ToolRegistry()
    rig_manager = _create_rig_manager(config)
    try:
        tool = SendAudioOverRadioTool(rig_manager=rig_manager, config=config)
        registry.register(tool)
        logger.debug("Tool registry created with tool: %s", tool.name)
    except Exception as e:
        logger.warning("Could not register SendAudioOverRadioTool: %s", e)
    callsign_repo = get_callsign_repository(db)
    try:
        registry.register(ListRegisteredCallsignsTool(callsign_repo))
        registry.register(RegisterCallsignTool(callsign_repo))
        logger.debug("Registered whitelist tools: list_registered_callsigns, register_callsign")
    except Exception as e:
        logger.warning("Could not register whitelist tools: %s", e)
    if db is not None:
        try:
            registry.register(SetOperatorLocationTool(db))
            registry.register(GetOperatorLocationTool(db))
            registry.register(OperatorsNearbyTool(db))
            logger.debug("Registered GIS tools: set_operator_location, get_operator_location, operators_nearby")
        except Exception as e:
            logger.warning("Could not register GIS tools: %s", e)
    if getattr(config, "memory", None) and getattr(config.memory, "enabled", False):
        try:
            from types import SimpleNamespace
            memory_cfg = get_memory_config_for_role(config, "memory")
            tools_config = SimpleNamespace(memory=memory_cfg)
            registry.register(RecallMemoryTool(tools_config))
            registry.register(ReflectMemoryTool(tools_config))
            logger.debug("Registered memory tools: recall_memory, reflect_memory")
        except Exception as e:
            logger.warning("Could not register memory tools: %s", e)
    if db is not None and app is not None:
        try:
            from radioshaq.database.transcripts import TranscriptStorage
            from radioshaq.radio.injection import get_injection_queue
            storage = TranscriptStorage(db=db)
            injection_queue = get_injection_queue()
            get_radio_tx = lambda: (
                app.state.agent_registry.get_agent("radio_tx")
                if getattr(app.state, "agent_registry", None) else None
            )
            relay_tool = RelayMessageTool(
                storage=storage,
                injection_queue=injection_queue,
                get_radio_tx=get_radio_tx,
                config=config,
                callsign_repository=callsign_repo,
            )
            registry.register(relay_tool)
            logger.debug("Registered relay tool: %s", relay_tool.name)
        except Exception as e:
            logger.warning("Could not register RelayMessageTool: %s", e)
    return registry


def create_middleware_pipeline(
    config: Config,
    *,
    max_turns: int | None = None,
    max_tokens: int = 50_000,
) -> Any:
    """Build MiddlewarePipeline with TurnLimit and TokenLimit. Optional for REACT loop."""
    from radioshaq.vendor.vibe.middleware import (
        MiddlewarePipeline,
        TurnLimitMiddleware,
        TokenLimitMiddleware,
    )
    pipeline = MiddlewarePipeline()
    turns = max_turns if max_turns is not None else getattr(config, "max_iterations", 20) or 20
    pipeline.add(TurnLimitMiddleware(max_turns=turns))
    pipeline.add(TokenLimitMiddleware(max_tokens=max_tokens))
    return pipeline


def create_orchestrator(
    config: Config,
    db: Any = None,
    message_bus: Any = None,
    memory_manager: Any = None,
    max_iterations: int = 20,
    middleware_pipeline: Any = None,
    tool_registry: Any = None,
    llm_client: Any = None,
) -> REACTOrchestrator:
    """Build REACTOrchestrator with Judge, PromptLoader, AgentRegistry, and optional middleware.
    Optionally store message_bus for future bridge use.
    When tool_registry and llm_client are provided, REASONING runs the LLM tool-calling loop.
    When memory_manager is provided, orchestrator loads/persists memory and retains to Hindsight per callsign.
    """
    judge = create_judge(config)
    agent_registry = create_agent_registry(config, db, message_bus=message_bus)
    prompts_dir = _prompts_dir()
    prompt_loader = PromptLoader(prompts_dir=prompts_dir)
    if middleware_pipeline is None:
        middleware_pipeline = create_middleware_pipeline(
            config, max_turns=max_iterations, max_tokens=50_000
        )
    if llm_client is None and tool_registry is not None:
        llm_cfg = get_llm_config_for_role(config, "orchestrator")
        llm_client = LLMClient(
            model=_llm_model_string_from_llm_config(llm_cfg),
            api_key=_llm_api_key_from_llm_config(llm_cfg),
            api_base=getattr(llm_cfg, "custom_api_base", None),
            temperature=getattr(llm_cfg, "temperature", 0.1),
            max_tokens=getattr(llm_cfg, "max_tokens", 4096),
        )

    orchestrator = REACTOrchestrator(
        judge=judge,
        prompt_loader=prompt_loader,
        max_iterations=max_iterations,
        agent_registry=agent_registry,
        middleware_pipeline=middleware_pipeline,
        tool_registry=tool_registry,
        llm_client=llm_client,
        memory_manager=memory_manager,
        db=db,
    )
    setattr(orchestrator, "_config", config)
    if message_bus is not None:
        setattr(orchestrator, "_message_bus", message_bus)
    from radioshaq.callsign.repository import get_callsign_repository
    setattr(orchestrator, "_callsign_repository", get_callsign_repository(db))
    return orchestrator
