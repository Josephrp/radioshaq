"""Config API: LLM, memory, and per-role overrides (GET/PATCH, keys redacted)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

from radioshaq.api.dependencies import get_config, get_current_user
from radioshaq.auth.jwt import TokenPayload
from radioshaq.config.schema import Config

router = APIRouter(prefix="", tags=["config"])

# Keys to redact in LLM config responses
_LLM_SECRET_KEYS = {"mistral_api_key", "openai_api_key", "anthropic_api_key", "custom_api_key"}


def _llm_config_dict(config: Config, redact: bool = True) -> dict[str, Any]:
    """Serialize LLM config to dict; redact API keys if redact=True."""
    llm = getattr(config, "llm", None)
    if not llm:
        return {}
    out = llm.model_dump(mode="json")
    if redact:
        for k in _LLM_SECRET_KEYS:
            if k in out and out[k] is not None and str(out[k]).strip():
                out[k] = "(set)"
    return out


def _memory_config_dict(config: Config) -> dict[str, Any]:
    """Serialize memory config to dict."""
    memory = getattr(config, "memory", None)
    if not memory:
        return {}
    return memory.model_dump(mode="json")


def _overrides_dict(config: Config) -> dict[str, Any]:
    """Return llm_overrides and memory_overrides."""
    return {
        "llm_overrides": getattr(config, "llm_overrides", None) or {},
        "memory_overrides": getattr(config, "memory_overrides", None) or {},
    }


@router.get("/config/llm")
async def get_config_llm(
    request: Request,
    config: Config = Depends(get_config),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Get current LLM configuration (API keys redacted). Runtime overrides merged if set."""
    out = _llm_config_dict(config, redact=True)
    override = getattr(request.app.state, "llm_config_override", None)
    if override:
        for k in _LLM_SECRET_KEYS:
            override.pop(k, None)
        out = {**out, **override}
    return out


@router.patch("/config/llm")
async def update_config_llm(
    request: Request,
    body: dict[str, Any],
    config: Config = Depends(get_config),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Update LLM configuration (runtime overlay only; does not persist to file). API keys in body are not stored."""
    if not hasattr(request.app.state, "llm_config_override"):
        request.app.state.llm_config_override = {}
    for k in _LLM_SECRET_KEYS:
        body.pop(k, None)
    request.app.state.llm_config_override.update(body)
    base = _llm_config_dict(config, redact=True)
    return {**base, **request.app.state.llm_config_override}


@router.get("/config/memory")
async def get_config_memory(
    request: Request,
    config: Config = Depends(get_config),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Get current memory/Hindsight configuration. Runtime overrides merged if set."""
    out = _memory_config_dict(config)
    override = getattr(request.app.state, "memory_config_override", None)
    if override:
        out = {**out, **override}
    return out


@router.patch("/config/memory")
async def update_config_memory(
    request: Request,
    body: dict[str, Any],
    config: Config = Depends(get_config),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Update memory configuration (runtime overlay only; does not persist to file)."""
    if not hasattr(request.app.state, "memory_config_override"):
        request.app.state.memory_config_override = {}
    request.app.state.memory_config_override.update(body)
    base = _memory_config_dict(config)
    return {**base, **request.app.state.memory_config_override}


@router.get("/config/overrides")
async def get_config_overrides(
    request: Request,
    config: Config = Depends(get_config),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Get per-role LLM and memory overrides. Keys: orchestrator, judge, whitelist, daily_summary, memory."""
    out = _overrides_dict(config)
    override = getattr(request.app.state, "config_overrides_override", None)
    if override:
        out = {**out, **override}
    return out


@router.patch("/config/overrides")
async def update_config_overrides(
    request: Request,
    body: dict[str, Any],
    config: Config = Depends(get_config),
    _user: TokenPayload = Depends(get_current_user),
) -> dict[str, Any]:
    """Update per-role overrides (runtime overlay only; does not persist to file)."""
    if not hasattr(request.app.state, "config_overrides_override"):
        request.app.state.config_overrides_override = {"llm_overrides": {}, "memory_overrides": {}}
    if "llm_overrides" in body and isinstance(body["llm_overrides"], dict):
        request.app.state.config_overrides_override.setdefault("llm_overrides", {}).update(body["llm_overrides"])
    if "memory_overrides" in body and isinstance(body["memory_overrides"], dict):
        request.app.state.config_overrides_override.setdefault("memory_overrides", {}).update(body["memory_overrides"])
    base = _overrides_dict(config)
    o = request.app.state.config_overrides_override
    return {"llm_overrides": {**base.get("llm_overrides", {}), **o.get("llm_overrides", {})}, "memory_overrides": {**base.get("memory_overrides", {}), **o.get("memory_overrides", {})}}
