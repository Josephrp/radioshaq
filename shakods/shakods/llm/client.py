"""LLM client using LiteLLM for provider-agnostic chat."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class ChatMessage:
    """Simple chat message for LLM."""

    role: str
    content: str


@dataclass
class ChatResponse:
    """Response from LLM chat."""

    content: str
    model: str = ""
    usage: dict[str, int] | None = None


class LLMClient:
    """LLM client using LiteLLM (supports Mistral, OpenAI, Anthropic, etc.)."""

    def __init__(
        self,
        model: str = "mistral/mistral-large-latest",
        api_key: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ):
        # Ensure litellm format: provider/model (e.g. mistral/mistral-large-latest)
        if "/" not in model and not model.startswith(("openai/", "anthropic/", "mistral/")):
            self.model = f"mistral/{model}"
        else:
            self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        """Send chat messages and return response."""
        import os

        import litellm

        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        api_key = self.api_key or os.environ.get("MISTRAL_API_KEY") or os.environ.get("OPENAI_API_KEY")

        try:
            completion = await litellm.acompletion(
                model=self.model,
                messages=messages,
                temperature=temp,
                max_tokens=max_tok,
                api_key=api_key,
            )
            choice = completion.choices[0] if completion.choices else None
            content = choice.message.content if choice and choice.message else ""
            return ChatResponse(
                content=content,
                model=getattr(completion, "model", self.model),
                usage=getattr(completion, "usage", None) and {
                    "prompt_tokens": getattr(completion.usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(completion.usage, "completion_tokens", 0),
                },
            )
        except Exception as e:
            logger.error("LLM chat failed: %s", e)
            raise
