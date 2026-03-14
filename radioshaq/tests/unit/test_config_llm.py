"""Unit tests for LLM config schema (LLMConfig, Hugging Face provider)."""

from __future__ import annotations

import pytest

from radioshaq.config.schema import LLMConfig, LLMProvider


def test_llm_config_has_huggingface_provider():
    """LLMProvider includes huggingface."""
    assert LLMProvider.HUGGINGFACE == "huggingface"


def test_llm_config_huggingface_fields():
    """LLMConfig has huggingface_api_key and huggingface_api_base, default None."""
    c = LLMConfig()
    assert getattr(c, "huggingface_api_key", None) is None
    assert getattr(c, "huggingface_api_base", None) is None


def test_llm_config_accepts_huggingface_provider():
    """LLMConfig accepts provider=huggingface and model."""
    c = LLMConfig(provider=LLMProvider.HUGGINGFACE, model="Qwen/Qwen2.5-7B-Instruct-1M")
    assert c.provider == LLMProvider.HUGGINGFACE
    assert c.model == "Qwen/Qwen2.5-7B-Instruct-1M"


def test_llm_config_huggingface_api_base_optional():
    """LLMConfig accepts huggingface_api_base."""
    c = LLMConfig(
        provider=LLMProvider.HUGGINGFACE,
        huggingface_api_base="https://router.huggingface.co/v1",
    )
    assert c.huggingface_api_base == "https://router.huggingface.co/v1"


def test_llm_config_has_gemini_provider():
    """LLMProvider includes gemini."""
    assert LLMProvider.GEMINI == "gemini"


def test_llm_config_gemini_fields():
    """LLMConfig accepts provider=gemini, model, and gemini_api_key."""
    c = LLMConfig(
        provider=LLMProvider.GEMINI,
        model="gemini-2.5-flash",
        gemini_api_key="test-key",
    )
    assert c.provider == LLMProvider.GEMINI
    assert c.model == "gemini-2.5-flash"
    assert c.gemini_api_key == "test-key"
