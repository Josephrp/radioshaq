"""Unit tests for REACT orchestrator and judge."""

import pytest

from shakods.orchestrator import (
    REACTPhase,
    REACTState,
    REACTOrchestrator,
    JudgeSystem,
    TaskEvaluation,
    DecomposedTask,
    AgentRegistry,
)
from shakods.prompts import PromptLoader


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
async def test_radio_tx_compliance_rejects_restricted_frequency():
    """RadioTransmissionAgent returns error when frequency is in restricted band."""
    from types import SimpleNamespace
    from shakods.specialized.radio_tx import RadioTransmissionAgent

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
