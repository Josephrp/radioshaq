"""Memory tools for orchestrator (LLM-callable): recall_memory, reflect_memory.

Allow the agent to query semantic memory (Hindsight) for the current operator.
Callsign is injected from request context when the tool is executed.
"""

from __future__ import annotations

import asyncio
from typing import Any

from radioshaq.memory.hindsight import recall, reflect

BUDGET_DESCRIPTION = (
    "Query depth: 'low' (fast, fewer results), 'mid' (balanced), 'high' (thorough, more latency)."
)


class RecallMemoryTool:
    """Tool: semantic recall over the current operator's memory (Hindsight)."""

    name = "recall_memory"
    description = (
        "Search my semantic memory about the current operator. Use when you need to remember "
        "past conversations, preferences, or facts about them. Returns relevant recalled memories. "
        "Requires the request to be associated with a callsign (injected automatically)."
    )

    def __init__(self, config: Any = None) -> None:
        self.config = getattr(config, "memory", None) if config else None

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language question to search memory (e.g. 'What rig does the operator use?').",
                        },
                        "budget": {
                            "type": "string",
                            "enum": ["low", "mid", "high"],
                            "description": BUDGET_DESCRIPTION,
                            "default": "mid",
                        },
                        "callsign": {
                            "type": "string",
                            "description": "Operator callsign (usually injected from context; omit unless overriding).",
                        },
                    },
                    "required": ["query"],
                },
            },
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        if not params.get("query") or not str(params.get("query", "")).strip():
            return ["query is required"]
        budget = params.get("budget")
        if budget is not None and budget not in ("low", "mid", "high"):
            return ["budget must be one of: low, mid, high"]
        return []

    async def execute(
        self,
        query: str,
        budget: str = "mid",
        callsign: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not (callsign and str(callsign).strip()):
            return "Error: No callsign in context. Memory recall is only available for identified operators."
        return await asyncio.to_thread(
            recall,
            callsign.strip().upper(),
            query.strip(),
            budget=budget,
            config=self.config,
        )


class ReflectMemoryTool:
    """Tool: deeper reflection over the current operator's memory (Hindsight)."""

    name = "reflect_memory"
    description = (
        "Reflect on my semantic memory about the current operator to synthesize patterns, "
        "insights, or summaries. Use when you need a higher-level view than recall. "
        "Requires the request to be associated with a callsign (injected automatically)."
    )

    def __init__(self, config: Any = None) -> None:
        self.config = getattr(config, "memory", None) if config else None

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Question to reflect on (e.g. 'What do you know about this operator?').",
                        },
                        "budget": {
                            "type": "string",
                            "enum": ["low", "mid", "high"],
                            "description": BUDGET_DESCRIPTION,
                            "default": "mid",
                        },
                        "callsign": {
                            "type": "string",
                            "description": "Operator callsign (usually injected from context; omit unless overriding).",
                        },
                    },
                    "required": ["query"],
                },
            },
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        if not params.get("query") or not str(params.get("query", "")).strip():
            return ["query is required"]
        budget = params.get("budget")
        if budget is not None and budget not in ("low", "mid", "high"):
            return ["budget must be one of: low, mid, high"]
        return []

    async def execute(
        self,
        query: str,
        budget: str = "mid",
        callsign: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not (callsign and str(callsign).strip()):
            return "Error: No callsign in context. Memory reflection is only available for identified operators."
        return await asyncio.to_thread(
            reflect,
            callsign.strip().upper(),
            query.strip(),
            budget=budget,
            config=self.config,
        )
