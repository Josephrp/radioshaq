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
class ToolCall:
    """Single tool call from LLM response (OpenAI/LiteLLM shape)."""

    id: str
    name: str
    arguments: str


@dataclass
class ChatResponse:
    """Response from LLM chat."""

    content: str
    model: str = ""
    usage: dict[str, int] | None = None


@dataclass
class ChatResponseWithTools(ChatResponse):
    """Response from chat_with_tools: may include tool_calls."""

    tool_calls: list[ToolCall] = ()


class LLMClient:
    """LLM client using LiteLLM (supports Mistral, OpenAI, Anthropic, etc.)."""

    def __init__(
        self,
        model: str = "mistral/mistral-large-latest",
        api_key: str | None = None,
        api_base: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ):
        # Ensure litellm format: provider/model (e.g. mistral/mistral-large-latest)
        if "/" not in model and not model.startswith(("openai/", "anthropic/", "mistral/", "custom/", "ollama/")):
            self.model = f"mistral/{model}"
        else:
            self.model = model
        self.api_key = api_key
        self.api_base = api_base
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
        api_key = (
            self.api_key
            or os.environ.get("MISTRAL_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("HF_TOKEN")
            or os.environ.get("HUGGINGFACE_API_KEY")
        )

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": max_tok,
            "api_key": api_key,
        }
        if self.api_base is not None:
            kwargs["api_base"] = self.api_base
        try:
            completion = await litellm.acompletion(**kwargs)
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
            logger.error("LLM chat failed: {}", e)
            raise

    async def chat_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        max_tool_rounds: int = 10,
    ) -> ChatResponseWithTools:
        """
        Send messages with tool definitions; return content and tool_calls.
        Does not loop; caller must execute tools, append results, and call again until no tool_calls.
        """
        import os

        import litellm

        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens
        api_key = (
            self.api_key
            or os.environ.get("MISTRAL_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("HF_TOKEN")
            or os.environ.get("HUGGINGFACE_API_KEY")
        )

        kwargs_tools: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": temp,
            "max_tokens": max_tok,
            "api_key": api_key,
        }
        if self.api_base is not None:
            kwargs_tools["api_base"] = self.api_base
        try:
            completion = await litellm.acompletion(**kwargs_tools)
            choice = completion.choices[0] if completion.choices else None
            msg = choice.message if choice and choice.message else None
            content = (msg.content or "").strip() if msg else ""
            tool_calls: list[ToolCall] = []
            raw_calls = getattr(msg, "tool_calls", None) if msg else None
            if raw_calls:
                for tc in raw_calls:
                    tid = getattr(tc, "id", None) or ""
                    name = ""
                    args = "{}"
                    if hasattr(tc, "function") and tc.function:
                        name = getattr(tc.function, "name", "") or ""
                        args = getattr(tc.function, "arguments", "") or "{}"
                    tool_calls.append(ToolCall(id=tid, name=name, arguments=args))
            return ChatResponseWithTools(
                content=content,
                model=getattr(completion, "model", self.model),
                usage=getattr(completion, "usage", None)
                and {
                    "prompt_tokens": getattr(completion.usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(completion.usage, "completion_tokens", 0),
                },
                tool_calls=tool_calls,
            )
        except Exception as e:
            logger.error("LLM chat_with_tools failed: {}", e)
            raise
