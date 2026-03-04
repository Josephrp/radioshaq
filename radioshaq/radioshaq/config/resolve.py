"""Resolve per-role LLM and memory config by merging global config with optional overrides."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from radioshaq.config.schema import Config

from radioshaq.config.schema import LLMConfig, MemoryConfig


def get_llm_config_for_role(config: Config, role: str) -> LLMConfig:
    """Return LLM config for the given role. Merges config.llm with config.llm_overrides[role]."""
    base = config.llm.model_dump()
    overrides = getattr(config, "llm_overrides", None) or {}
    role_overrides = overrides.get(role) if isinstance(overrides, dict) else None
    if role_overrides and isinstance(role_overrides, dict):
        for k, v in role_overrides.items():
            if k in base and v is not None:
                base[k] = v
    return LLMConfig(**base)


def get_memory_config_for_role(config: Config, role: str) -> MemoryConfig:
    """Return memory config for the given role. Merges config.memory with config.memory_overrides[role]."""
    base = config.memory.model_dump()
    overrides = getattr(config, "memory_overrides", None) or {}
    role_overrides = overrides.get(role) if isinstance(overrides, dict) else None
    if role_overrides and isinstance(role_overrides, dict):
        for k, v in role_overrides.items():
            if k in base and v is not None:
                base[k] = v
    return MemoryConfig(**base)
