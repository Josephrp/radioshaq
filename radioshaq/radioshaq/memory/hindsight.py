"""Hindsight integration: semantic memory per callsign bank.

Each callsign gets a unique bank_id (radioshaq-{CALLSIGN}).
Retain exchanges, recall, and reflect via the Hindsight HTTP service.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from radioshaq.config.schema import MemoryConfig


def _get_bank_id(callsign: str) -> str:
    """Build Hindsight bank_id for a callsign."""
    c = (callsign or "").strip().upper() or "UNKNOWN"
    return f"radioshaq-{c}"


def _get_base_url(config: MemoryConfig | None = None) -> str:
    """Base URL for Hindsight API; config overrides env."""
    if config is not None:
        return getattr(config, "hindsight_base_url", None) or "http://localhost:8888"
    return os.environ.get("RADIOSHAQ_MEMORY__HINDSIGHT_BASE_URL") or os.environ.get(
        "HINDSIGHT_BASE_URL", "http://localhost:8888"
    )


def _get_client(config: MemoryConfig | None = None):
    """Lazy-import and create Hindsight client."""
    try:
        from hindsight_client import Hindsight
        return Hindsight(base_url=_get_base_url(config))
    except ImportError:
        return None


def _is_enabled(config: MemoryConfig | None = None) -> bool:
    """Check if Hindsight is enabled; config overrides env."""
    if config is not None:
        return getattr(config, "hindsight_enabled", True)
    raw = (
        os.environ.get("RADIOSHAQ_MEMORY__HINDSIGHT_ENABLED")
        or os.environ.get("HINDSIGHT_ENABLED", "true")
    )
    return (raw or "true").lower() in ("true", "1", "yes")


def _format_as_lived_experience(
    user_content: str, assistant_content: str | None, callsign: str
) -> str:
    """Format a user/assistant exchange as the AI's lived experience."""
    user_content = (user_content or "").strip()
    assistant_content = (assistant_content or "").strip() if assistant_content else None
    callsign = (callsign or "operator").upper()

    if assistant_content:
        return (
            f"The operator {callsign} and I were in conversation. They said: \"{user_content}\" "
            f"I responded: \"{assistant_content}\""
        )
    return f"The operator {callsign} reached out. They said: \"{user_content}\""


def retain_exchange(
    callsign: str,
    user_content: str,
    assistant_content: str | None = None,
    *,
    document_id: str | None = None,
    config: MemoryConfig | None = None,
) -> bool:
    """
    Retain a user/assistant exchange into Hindsight as lived experience.
    Returns True if retained, False if Hindsight unavailable or disabled.
    Optional document_id: if provided, Hindsight upserts (replaces) by this ID.
    """
    if not _is_enabled(config):
        return False

    client = _get_client(config)
    if not client:
        logger.debug("Hindsight client not available (hindsight-client not installed)")
        return False

    bank_id = _get_bank_id(callsign)
    content = _format_as_lived_experience(user_content, assistant_content, callsign)
    c_upper = (callsign or "").strip().upper()

    try:
        with client:
            kwargs: dict[str, Any] = {
                "bank_id": bank_id,
                "content": content,
                "context": "conversation",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": {"callsign": c_upper},
                "tags": [f"user:{c_upper}", "channel:radioshaq"],
            }
            if document_id is not None:
                kwargs["document_id"] = document_id
            client.retain(**kwargs)
        return True
    except Exception as e:
        logger.warning("Hindsight retain failed: %s", e)
        return False


async def aretain_exchange(
    callsign: str,
    user_content: str,
    assistant_content: str | None = None,
    *,
    document_id: str | None = None,
    config: MemoryConfig | None = None,
) -> bool:
    """
    Async retain: runs sync retain_exchange in a thread so the request path doesn't block.
    """
    return await asyncio.to_thread(
        retain_exchange,
        callsign,
        user_content,
        assistant_content,
        document_id=document_id,
        config=config,
    )


def recall(
    callsign: str,
    query: str,
    *,
    budget: str = "mid",
    max_tokens: int | None = None,
    config: MemoryConfig | None = None,
) -> str:
    """
    Recall memories from Hindsight for a callsign.
    budget: "low" (fast), "mid" (balanced), "high" (thorough).
    """
    client = _get_client(config)
    if not client:
        return "Hindsight is not available. Memory recall failed."

    bank_id = _get_bank_id(callsign)
    try:
        with client:
            kwargs: dict[str, Any] = {"bank_id": bank_id, "query": query, "budget": budget}
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            try:
                response = client.recall(**kwargs)
            except TypeError:
                kwargs.pop("max_tokens", None)
                kwargs.pop("budget", None)
                response = client.recall(bank_id=bank_id, query=query)
        results = getattr(response, "results", []) or []
        if not results:
            return "I don't have any memories that match that."

        texts = []
        for r in results:
            text = getattr(r, "text", None) or (str(r) if r else None)
            if text and isinstance(text, str) and text.strip():
                texts.append(text.strip())

        if not texts:
            return "I don't have any memories that match that."

        return "From my experience with this operator:\n\n" + "\n\n".join(texts)
    except Exception as e:
        return f"Hindsight recall failed: {e}"


def reflect(
    callsign: str,
    query: str,
    *,
    budget: str = "mid",
    config: MemoryConfig | None = None,
) -> str:
    """
    Reflect on memories — deeper synthesis, patterns, insights.
    budget: "low" (fast), "mid" (balanced), "high" (thorough).
    """
    client = _get_client(config)
    if not client:
        return "Hindsight is not available. Reflection failed."

    bank_id = _get_bank_id(callsign)
    try:
        with client:
            try:
                answer = client.reflect(bank_id=bank_id, query=query, budget=budget)
            except TypeError:
                answer = client.reflect(bank_id=bank_id, query=query)
        text = getattr(answer, "text", None) or (str(answer) if answer else None)
        return (text or "").strip() or "I reflected but have nothing specific to share."
    except Exception as e:
        return f"Hindsight reflect failed: {e}"
