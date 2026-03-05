"""Judge system for task and subtask evaluation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from loguru import logger

from radioshaq.orchestrator.react_loop import REACTState, DecomposedTask


@dataclass
class TaskEvaluation:
    """Result of task completion evaluation."""

    is_complete: bool
    confidence: float
    reasoning: str
    missing_elements: list[str]
    quality_score: float
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


class LLMProviderProtocol(Protocol):
    """Protocol for LLM providers used by the judge."""

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        """Send chat and return response with .content attribute."""
        ...


class JudgeSystem:
    """Multi-level judge system for evaluating task completion."""

    def __init__(
        self,
        provider: LLMProviderProtocol,
        task_judge_prompt: str,
        subtask_judge_prompt: str,
        quality_threshold: float = 0.7,
    ):
        self.provider = provider
        self.task_judge_prompt = task_judge_prompt
        self.subtask_judge_prompt = subtask_judge_prompt
        self.quality_threshold = quality_threshold

    async def evaluate_task_completion(self, state: REACTState) -> TaskEvaluation:
        """Orchestrator-level judge: Has the overall task been completed?"""
        prompt = self._build_task_evaluation_prompt(state)
        system_content = self.task_judge_prompt
        if state.context.get("memory_system_prefix"):
            system_content = state.context["memory_system_prefix"] + "\n\n" + system_content

        response = await self.provider.chat(
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1024,
        )

        content = getattr(response, "content", str(response))
        return self._parse_task_evaluation(content, state)

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
Respond with structured JSON only, no markdown:
{{"is_complete": true|false, "confidence": 0.0-1.0, "reasoning": "...", "missing_elements": ["..."], "quality_score": 0.0-1.0, "next_action": "..."}}
"""

    def _format_tasks(self, tasks: list[DecomposedTask]) -> str:
        lines = []
        for t in tasks:
            lines.append(f"  - [{t.task_id}] {t.description} (status={t.status})")
            if t.result:
                lines.append(f"    result: {json.dumps(t.result)[:200]}")
        return "\n".join(lines) if lines else "  (none)"

    def _parse_task_evaluation(self, content: str, state: REACTState) -> TaskEvaluation:
        """Parse LLM response into TaskEvaluation."""
        default = TaskEvaluation(
            is_complete=len(state.completed_tasks) >= len(state.decomposed_tasks)
            and not state.decomposed_tasks,
            confidence=0.5,
            reasoning="Parse failed, using heuristic",
            missing_elements=[],
            quality_score=0.5,
            next_action="Continue REACT loop",
        )

        try:
            json_str = self._extract_json(content)
            if not json_str:
                return default
            data = json.loads(json_str)
            return TaskEvaluation(
                is_complete=bool(data.get("is_complete", False)),
                confidence=float(data.get("confidence", 0.5)),
                reasoning=str(data.get("reasoning", "")),
                missing_elements=list(data.get("missing_elements", [])),
                quality_score=float(data.get("quality_score", 0.5)),
                next_action=data.get("next_action"),
            )
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning("Failed to parse task evaluation: %s", e)
            return default

    def _extract_json(self, text: str) -> str | None:
        """Extract JSON object from text (handles markdown code blocks)."""
        text = text.strip()
        match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
        if match:
            return match.group(1)
        match = re.search(r"(\{[\s\S]*\})", text)
        if match:
            return match.group(1)
        return None

    async def evaluate_subtask(
        self,
        subtask_id: str,
        description: str,
        result: dict[str, Any] | None,
        error: str | None,
    ) -> SubtaskEvaluation:
        """Evaluate a single subtask's execution quality."""
        prompt = f"""
Evaluate subtask execution:

Subtask ID: {subtask_id}
Description: {description}
Result: {json.dumps(result or {})}
Error: {error or "None"}

Respond with structured JSON only:
{{"success": true|false, "output_quality": 0.0-1.0, "errors": ["..."], "recommendations": ["..."], "retry_eligible": true|false}}
"""

        try:
            response = await self.provider.chat(
                messages=[
                    {"role": "system", "content": self.subtask_judge_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=512,
            )
            content = getattr(response, "content", str(response))
            json_str = self._extract_json(content)
            if json_str:
                data = json.loads(json_str)
                return SubtaskEvaluation(
                    subtask_id=subtask_id,
                    success=bool(data.get("success", False)),
                    output_quality=float(data.get("output_quality", 0.5)),
                    errors=list(data.get("errors", [])),
                    recommendations=list(data.get("recommendations", [])),
                    retry_eligible=bool(data.get("retry_eligible", False)),
                )
        except Exception as e:
            logger.warning("Subtask evaluation failed: %s", e)

        return SubtaskEvaluation(
            subtask_id=subtask_id,
            success=error is None,
            output_quality=0.5,
            errors=[error] if error else [],
            recommendations=[],
            retry_eligible=bool(error),
        )

    def passes_quality_gate(self, evaluation: TaskEvaluation) -> bool:
        """Check if evaluation meets quality threshold."""
        return (
            evaluation.is_complete
            and evaluation.confidence >= self.quality_threshold
            and evaluation.quality_score >= self.quality_threshold
        )
