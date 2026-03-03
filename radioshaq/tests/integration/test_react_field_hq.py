"""Integration tests: REACT loop and field-HQ flow (optional DB)."""

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_react_loop_with_mock_llm():
    """REACT orchestrator runs to completion with mock judge/LLM."""
    from radioshaq.orchestrator import REACTOrchestrator, REACTState, REACTPhase
    from radioshaq.orchestrator.judge import JudgeSystem, TaskEvaluation
    from radioshaq.prompts import PromptLoader

    class MockLLM:
        async def chat(self, messages, temperature=None, max_tokens=None):
            from types import SimpleNamespace
            return SimpleNamespace(
                content='{"is_complete": true, "confidence": 0.9, "reasoning": "Done", '
                '"missing_elements": [], "quality_score": 0.9, "next_action": null}'
            )

    loader = PromptLoader()
    task_prompt = loader.load_raw("judges/task_completion")
    subtask_prompt = loader.load_raw("judges/subtask_quality")
    judge = JudgeSystem(MockLLM(), task_prompt, subtask_prompt)
    orchestrator = REACTOrchestrator(judge=judge, prompt_loader=loader, max_iterations=3)
    result = await orchestrator.process_request("Schedule a net on 40m")
    assert result.success is True
    assert result.state.phase in (REACTPhase.TRACKING, REACTPhase.COMMUNICATING, REACTPhase.REASONING)
    assert len(result.message) >= 0
