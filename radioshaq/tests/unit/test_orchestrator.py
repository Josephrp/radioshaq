"""Unit tests for REACT orchestrator and judge."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from radioshaq.orchestrator import (
    REACTPhase,
    REACTState,
    REACTOrchestrator,
    JudgeSystem,
    TaskEvaluation,
    SubtaskEvaluation,
    DecomposedTask,
    AgentRegistry,
)
from radioshaq.prompts import PromptLoader


class MockLLMProvider:
    """Mock LLM that returns structured JSON for judge evaluation."""

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        from types import SimpleNamespace

        return SimpleNamespace(
            content='{"is_complete": true, "confidence": 0.9, "reasoning": "All done", '
            '"missing_elements": [], "quality_score": 0.85, "next_action": null}'
        )


@pytest.fixture
def mock_judge():
    """Create JudgeSystem with mock LLM."""
    loader = PromptLoader()
    task_prompt = loader.load_raw("judges/task_completion")
    subtask_prompt = loader.load_raw("judges/subtask_quality")
    provider = MockLLMProvider()
    return JudgeSystem(provider, task_prompt, subtask_prompt)


@pytest.fixture
def mock_orchestrator(mock_judge):
    """Create REACTOrchestrator with mock judge."""
    loader = PromptLoader()
    return REACTOrchestrator(judge=mock_judge, prompt_loader=loader, max_iterations=5)


@pytest.mark.asyncio
async def test_react_state_creation():
    """REACTState initializes correctly."""
    state = REACTState(
        task_id="t1",
        original_request="Schedule a call",
        phase=REACTPhase.REASONING,
    )
    assert state.task_id == "t1"
    assert state.phase == REACTPhase.REASONING
    assert state.iteration == 0


@pytest.mark.asyncio
async def test_judge_evaluate_task_completion(mock_judge):
    """JudgeSystem.evaluate_task_completion returns TaskEvaluation."""
    state = REACTState(
        task_id="t1",
        original_request="Test request",
        decomposed_tasks=[
            DecomposedTask("t1", "Do something", None, status="completed"),
        ],
        completed_tasks=[
            DecomposedTask("t1", "Do something", None, status="completed"),
        ],
    )
    evaluation = await mock_judge.evaluate_task_completion(state)
    assert isinstance(evaluation, TaskEvaluation)
    assert evaluation.is_complete is True
    assert evaluation.confidence >= 0.8


@pytest.mark.asyncio
async def test_orchestrator_process_request(mock_orchestrator):
    """REACTOrchestrator processes request and returns result."""
    result = await mock_orchestrator.process_request("Schedule a call with K5ABC")
    assert result.success is True
    assert "Processed" in result.message or len(result.message) > 0


def test_agent_registry_register_and_get():
    """AgentRegistry registers agents and retrieves by capability."""

    class MockAgent:
        name = "radio_tx"
        description = "Transmits via ham radio"
        capabilities = ["voice_transmission", "digital_mode_transmission"]

    registry = AgentRegistry()
    agent = MockAgent()
    registry.register_agent(agent)

    assert registry.get_agent("radio_tx") is agent
    assert registry.get_agent_for_task({"capability": "voice_transmission"}) is agent
    assert registry.get_agent_for_task({"transmission_type": "voice"}) is agent
    assert registry.list_capabilities()["voice_transmission"] == ["radio_tx"]


@pytest.mark.asyncio
async def test_communicating_uses_last_llm_reply(mock_orchestrator):
    """COMMUNICATING sets final_response from context last_llm_reply first."""
    state = REACTState(
        task_id="t1",
        original_request="Test",
        phase=REACTPhase.COMMUNICATING,
        completed_tasks=[],
    )
    state.context["last_llm_reply"] = "Done."
    await mock_orchestrator._phase_communicating(state)
    assert state.final_response == "Done."


@pytest.mark.asyncio
async def test_parse_decomposed_tasks_from_llm(mock_orchestrator):
    """_parse_decomposed_tasks_from_llm parses valid JSON into DecomposedTask list."""
    content = '''
    {"decomposed_tasks": [
        {"id": "a1", "description": "Send message", "agent": "radio_tx", "payload": {"frequency_hz": 7200000}}
    ]}
    '''
    tasks = mock_orchestrator._parse_decomposed_tasks_from_llm(content, "Original request")
    assert len(tasks) == 1
    assert tasks[0].task_id == "a1"
    assert tasks[0].description == "Send message"
    assert tasks[0].agent == "radio_tx"
    assert tasks[0].payload.get("frequency_hz") == 7200000
    assert tasks[0].status == "pending"


@pytest.mark.asyncio
async def test_parse_decomposed_tasks_fallback(mock_orchestrator):
    """_parse_decomposed_tasks_from_llm returns single task on invalid input."""
    tasks = mock_orchestrator._parse_decomposed_tasks_from_llm("not json", "Fallback request")
    assert len(tasks) == 1
    assert tasks[0].description == "Fallback request"
    assert tasks[0].agent is None


@pytest.mark.asyncio
async def test_evaluation_persists_last_evaluation(mock_orchestrator):
    """EVALUATION branch stores last_evaluation in state.context."""
    state = REACTState(
        task_id="t1",
        original_request="Test",
        phase=REACTPhase.EVALUATION,
        decomposed_tasks=[],
        completed_tasks=[DecomposedTask("t1", "Done", None, status="completed")],
    )
    with patch.object(
        mock_orchestrator.judge,
        "evaluate_task_completion",
        new_callable=AsyncMock,
        return_value=TaskEvaluation(
            is_complete=True,
            confidence=0.9,
            reasoning="Done",
            missing_elements=[],
            quality_score=0.9,
            next_action=None,
        ),
    ):
        result = await mock_orchestrator._run_react_loop(state, None)
    assert "last_evaluation" in result.context
    assert result.context["last_evaluation"]["is_complete"] is True
    assert result.context["last_evaluation"]["confidence"] == 0.9


@pytest.mark.asyncio
async def test_acting_calls_subtask_judge(mock_judge):
    """ACTING calls evaluate_subtask after agent execution."""
    mock_agent = MagicMock()
    mock_agent.name = "test_agent"
    mock_agent.description = "Test"
    mock_agent.capabilities = ["test"]
    mock_agent.execute = AsyncMock(return_value={"message_for_user": "OK"})
    registry = AgentRegistry()
    registry.register_agent(mock_agent)
    loader = PromptLoader()
    orchestrator = REACTOrchestrator(
        judge=mock_judge,
        prompt_loader=loader,
        max_iterations=5,
        agent_registry=registry,
    )
    state = REACTState(
        task_id="t1",
        original_request="Run test",
        phase=REACTPhase.ACTING,
        decomposed_tasks=[
            DecomposedTask("t1", "Do test", "test_agent", status="pending"),
        ],
    )
    with patch.object(
        orchestrator.judge,
        "evaluate_subtask",
        new_callable=AsyncMock,
        return_value=SubtaskEvaluation(
            subtask_id="t1",
            success=True,
            output_quality=0.9,
            errors=[],
            recommendations=[],
            retry_eligible=False,
        ),
    ) as mock_subtask:
        await orchestrator._phase_acting(state)
    mock_subtask.assert_called_once()
    assert state.context.get("subtask_evaluations")
    assert len(state.completed_tasks) == 1


@pytest.mark.asyncio
async def test_radio_tx_compliance_rejects_restricted_frequency():
    """RadioTransmissionAgent returns error when frequency is in restricted band."""
    from types import SimpleNamespace
    from radioshaq.specialized.radio_tx import RadioTransmissionAgent

    config = SimpleNamespace(
        radio=SimpleNamespace(
            tx_allowed_bands_only=True,
            restricted_bands_region="FCC",
        ),
    )
    agent = RadioTransmissionAgent(rig_manager=None, config=config)
    task = {
        "transmission_type": "voice",
        "frequency": 115e6,  # 108-121.94 MHz restricted (FCC §15.205)
        "message": "test",
        "mode": "FM",
    }
    result = await agent.execute(task)
    assert result.get("success") is False
    assert "not allowed" in result.get("notes", "").lower() or "restricted" in result.get("notes", "").lower()


@pytest.mark.asyncio
async def test_radio_tx_explicit_use_tts_false_overrides_voice_use_tts_true():
    """Explicit task use_tts=False must disable TTS even when config.voice_use_tts=True."""
    from types import SimpleNamespace
    from radioshaq.specialized.radio_tx import RadioTransmissionAgent

    rig_manager = MagicMock()
    rig_manager.set_frequency = AsyncMock(return_value=None)
    rig_manager.set_mode = AsyncMock(return_value=None)
    rig_manager.set_ptt = AsyncMock(return_value=None)

    config = SimpleNamespace(
        radio=SimpleNamespace(
            tx_allowed_bands_only=False,
            voice_use_tts=True,
            sdr_tx_enabled=False,
            audio_output_device=None,
            tx_audit_log_path=None,
        ),
    )
    agent = RadioTransmissionAgent(rig_manager=rig_manager, config=config)
    task = {
        "transmission_type": "voice",
        "frequency": 145_550_000.0,
        "message": "should not synthesize",
        "mode": "FM",
        "use_tts": False,
    }
    result = await agent.execute(task)
    assert result.get("success") is True
    assert "PTT only" in result.get("notes", "")


@pytest.mark.asyncio
async def test_radio_tx_voice_without_explicit_frequency_or_mode_keeps_rig_settings():
    """Voice TX should not retune or remode when task omits frequency/mode."""
    from types import SimpleNamespace
    from radioshaq.specialized.radio_tx import RadioTransmissionAgent

    rig_manager = MagicMock()
    rig_manager.set_frequency = AsyncMock(return_value=None)
    rig_manager.set_mode = AsyncMock(return_value=None)
    rig_manager.set_ptt = AsyncMock(return_value=None)

    config = SimpleNamespace(
        radio=SimpleNamespace(
            tx_allowed_bands_only=False,
            voice_use_tts=False,
            sdr_tx_enabled=False,
            audio_output_device=None,
            tx_audit_log_path=None,
        ),
    )
    agent = RadioTransmissionAgent(rig_manager=rig_manager, config=config)
    task = {
        "transmission_type": "voice",
        "message": "use current rig settings",
    }

    result = await agent.execute(task)
    assert result.get("success") is True
    rig_manager.set_frequency.assert_not_awaited()
    rig_manager.set_mode.assert_not_awaited()


@pytest.mark.asyncio
async def test_radio_tx_voice_with_frequency_hz_none_normalizes_to_zero() -> None:
    """When frequency_hz is explicitly None, execute() should normalize it to 0.0."""
    from types import SimpleNamespace
    from radioshaq.specialized.radio_tx import RadioTransmissionAgent

    rig_manager = MagicMock()
    rig_manager.set_frequency = AsyncMock(return_value=None)
    rig_manager.set_mode = AsyncMock(return_value=None)
    rig_manager.set_ptt = AsyncMock(return_value=None)

    config = SimpleNamespace(
        radio=SimpleNamespace(
            tx_allowed_bands_only=False,
            voice_use_tts=False,
            sdr_tx_enabled=False,
            audio_output_device=None,
            tx_audit_log_path=None,
        ),
    )
    agent = RadioTransmissionAgent(rig_manager=rig_manager, config=config)
    task = {
        "transmission_type": "voice",
        "frequency_hz": None,
        "message": "normalize none",
    }

    result = await agent.execute(task)
    assert result.get("success") is True
    assert result.get("frequency") == 0.0
    rig_manager.set_frequency.assert_not_awaited()


@pytest.mark.asyncio
async def test_radio_tx_digital_does_not_retune_when_frequency_not_set():
    """Digital TX should not call set_frequency when task omits explicit frequency."""
    from types import SimpleNamespace
    from radioshaq.specialized.radio_tx import RadioTransmissionAgent

    rig_manager = MagicMock()
    rig_manager.set_frequency = AsyncMock(return_value=None)
    digital_modes = MagicMock()
    digital_modes.set_modem = AsyncMock(return_value=None)
    digital_modes.transmit_text = AsyncMock(return_value=None)

    config = SimpleNamespace(
        radio=SimpleNamespace(
            tx_allowed_bands_only=False,
            restricted_bands_region="FCC",
            sdr_tx_enabled=False,
        ),
    )
    agent = RadioTransmissionAgent(
        rig_manager=rig_manager,
        digital_modes=digital_modes,
        config=config,
    )
    task = {
        "transmission_type": "digital",
        "message": "CQ TEST",
        "digital_mode": "PSK31",
        # frequency intentionally omitted -> execute() resolves 0.0
    }
    result = await agent.execute(task)
    assert result.get("success") is True
    rig_manager.set_frequency.assert_not_awaited()
    digital_modes.set_modem.assert_awaited_once_with("PSK31")
    digital_modes.transmit_text.assert_awaited_once_with("CQ TEST")


# ---- GIS location capture: tool registry, agent routing, context injection ----

def test_tool_registry_includes_gis_tools_when_db_present():
    """create_tool_registry with db registers set_operator_location, get_operator_location, operators_nearby."""
    from radioshaq.config.schema import Config
    from radioshaq.orchestrator.factory import create_tool_registry

    config = Config()
    mock_db = MagicMock()
    registry = create_tool_registry(config, db=mock_db)
    assert registry.has("set_operator_location")
    assert registry.has("get_operator_location")
    assert registry.has("operators_nearby")
    assert "set_operator_location" in registry.tool_names
    assert "get_operator_location" in registry.tool_names
    assert "operators_nearby" in registry.tool_names


def test_get_agent_for_task_gis_returns_gis_agent():
    """get_agent_for_task with agent 'gis' returns GISAgent when registered."""
    from radioshaq.specialized.gis_agent import GISAgent

    registry = AgentRegistry()
    gis_agent = GISAgent(db=None)
    registry.register_agent(gis_agent)
    agent = registry.get_agent_for_task({"agent": "gis"})
    assert agent is gis_agent
    assert agent.name == "gis"


@pytest.mark.asyncio
async def test_inject_agent_context_injects_callsign_for_gis(mock_judge):
    """_inject_agent_context sets task_dict['callsign'] when agent is gis and payload has no callsign."""
    from radioshaq.specialized.gis_agent import GISAgent

    loader = PromptLoader()
    registry = AgentRegistry()
    registry.register_agent(GISAgent(db=None))
    orchestrator = REACTOrchestrator(
        judge=mock_judge,
        prompt_loader=loader,
        max_iterations=5,
        agent_registry=registry,
    )
    state = REACTState(
        task_id="t1",
        original_request="Where am I?",
        context={"callsign": "K5ABC"},
    )
    task_dict = {"agent": "gis", "action": "get_location"}
    orchestrator._inject_agent_context(state, task_dict)
    assert task_dict.get("callsign") == "K5ABC"


@pytest.mark.asyncio
async def test_gis_propagation_fallback_uses_stored_location():
    """GISAgent._propagation_prediction uses stored location as origin when origin coords are omitted (not when 0,0)."""
    from radioshaq.specialized.gis_agent import GISAgent

    mock_db = MagicMock()
    mock_db.get_latest_location_decoded = AsyncMock(
        return_value={"latitude": 48.8566, "longitude": 2.3522, "callsign": "K5ABC"}
    )
    agent = GISAgent(db=mock_db)
    # Omit latitude_origin/longitude_origin so fallback runs; explicit (0,0) would be valid and not trigger fallback
    task = {
        "latitude_destination": 40.0,
        "longitude_destination": -74.0,
        "callsign": "K5ABC",
    }
    result = await agent._propagation_prediction(task, None)
    assert result["success"] is True
    assert result["origin"]["latitude"] == 48.8566
    assert result["origin"]["longitude"] == 2.3522
    mock_db.get_latest_location_decoded.assert_awaited_once_with("K5ABC")


@pytest.mark.asyncio
async def test_gis_propagation_explicit_zero_zero_origin_not_overridden():
    """Explicit (0, 0) origin is used as-is; stored location is not substituted (0.0 is valid)."""
    from radioshaq.specialized.gis_agent import GISAgent

    mock_db = MagicMock()
    mock_db.get_latest_location_decoded = AsyncMock(
        return_value={"latitude": 48.8566, "longitude": 2.3522, "callsign": "K5ABC"}
    )
    agent = GISAgent(db=mock_db)
    task = {
        "latitude_origin": 0.0,
        "longitude_origin": 0.0,
        "latitude_destination": 40.0,
        "longitude_destination": -74.0,
        "callsign": "K5ABC",
    }
    result = await agent._propagation_prediction(task, None)
    assert result["success"] is True
    # Origin must remain (0, 0), not the stored location
    assert result["origin"]["latitude"] == 0.0
    assert result["origin"]["longitude"] == 0.0
    mock_db.get_latest_location_decoded.assert_not_awaited()
