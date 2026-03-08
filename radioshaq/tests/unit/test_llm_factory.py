"""Unit tests for LLM factory helpers (model string, api_base, api_key for huggingface)."""

from __future__ import annotations

import pytest

from radioshaq.config.schema import LLMConfig, LLMProvider
from radioshaq.orchestrator.factory import (
    _llm_api_base_for_provider,
    _llm_api_key_from_llm_config,
    _llm_model_string_from_llm_config,
)


def test_llm_model_string_huggingface_prefix():
    """When provider is huggingface, model without openai/ gets openai/ prefix."""
    llm = LLMConfig(provider=LLMProvider.HUGGINGFACE, model="Qwen/Qwen2.5-7B-Instruct-1M")
    assert _llm_model_string_from_llm_config(llm) == "openai/Qwen/Qwen2.5-7B-Instruct-1M"


def test_llm_model_string_huggingface_already_openai_prefix():
    """When provider is huggingface and model already starts with openai/, keep as-is."""
    llm = LLMConfig(provider=LLMProvider.HUGGINGFACE, model="openai/gpt-oss-120b:groq")
    assert _llm_model_string_from_llm_config(llm) == "openai/gpt-oss-120b:groq"


def test_llm_api_base_for_provider_huggingface_default():
    """When provider is huggingface and no base set, return HF router URL."""
    llm = LLMConfig(provider=LLMProvider.HUGGINGFACE)
    assert _llm_api_base_for_provider(llm) == "https://router.huggingface.co/v1"


def test_llm_api_base_for_provider_huggingface_custom_base():
    """When provider is huggingface with huggingface_api_base set, return it."""
    llm = LLMConfig(
        provider=LLMProvider.HUGGINGFACE,
        huggingface_api_base="https://custom.hf.router/v1",
    )
    assert _llm_api_base_for_provider(llm) == "https://custom.hf.router/v1"


def test_llm_api_base_for_provider_custom():
    """When provider is custom, return custom_api_base."""
    llm = LLMConfig(provider=LLMProvider.CUSTOM, custom_api_base="http://localhost:11434")
    assert _llm_api_base_for_provider(llm) == "http://localhost:11434"


def test_llm_api_base_for_provider_mistral_none():
    """When provider is mistral, return None."""
    llm = LLMConfig(provider=LLMProvider.MISTRAL)
    assert _llm_api_base_for_provider(llm) is None


def test_llm_api_key_from_llm_config_huggingface():
    """When provider is huggingface, return huggingface_api_key."""
    llm = LLMConfig(provider=LLMProvider.HUGGINGFACE, huggingface_api_key="hf_abc")
    assert _llm_api_key_from_llm_config(llm) == "hf_abc"


def test_llm_api_key_from_llm_config_mistral():
    """When provider is mistral, return mistral_api_key."""
    llm = LLMConfig(provider=LLMProvider.MISTRAL, mistral_api_key="sk-mistral")
    assert _llm_api_key_from_llm_config(llm) == "sk-mistral"


def test_llm_api_key_from_llm_config_provider_matched_only():
    """API key returned is for configured provider only (no cross-provider)."""
    llm = LLMConfig(
        provider=LLMProvider.HUGGINGFACE,
        mistral_api_key="sk-mistral",
        huggingface_api_key="hf_xyz",
    )
    assert _llm_api_key_from_llm_config(llm) == "hf_xyz"
