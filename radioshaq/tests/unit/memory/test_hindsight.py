"""Unit tests for radioshaq.memory.hindsight (mocked client)."""

from __future__ import annotations

import pytest

from radioshaq.memory.hindsight import (
    _get_bank_id,
    _is_enabled,
    recall,
    reflect,
    retain_exchange,
)


def test_get_bank_id() -> None:
    assert _get_bank_id("W1ABC") == "radioshaq-W1ABC"
    assert _get_bank_id("  k5xyz  ") == "radioshaq-K5XYZ"
    assert _get_bank_id("") == "radioshaq-UNKNOWN"


def test_is_enabled_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RADIOSHAQ_MEMORY__HINDSIGHT_ENABLED", raising=False)
    monkeypatch.delenv("HINDSIGHT_ENABLED", raising=False)
    assert _is_enabled(None) is True
    monkeypatch.setenv("HINDSIGHT_ENABLED", "false")
    assert _is_enabled(None) is False
    monkeypatch.setenv("RADIOSHAQ_MEMORY__HINDSIGHT_ENABLED", "true")
    assert _is_enabled(None) is True


def test_retain_exchange_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HINDSIGHT_ENABLED", "false")
    assert retain_exchange("W1ABC", "Hello", "Hi there") is False


def test_retain_exchange_no_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HINDSIGHT_ENABLED", "true")
    monkeypatch.setattr(
        "radioshaq.memory.hindsight._get_client",
        lambda config=None: None,
    )
    assert retain_exchange("W1ABC", "Hello", "Hi") is False


def test_recall_no_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "radioshaq.memory.hindsight._get_client",
        lambda config=None: None,
    )
    result = recall("W1ABC", "What rig?")
    assert "not available" in result.lower() or "failed" in result.lower()


def test_reflect_no_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "radioshaq.memory.hindsight._get_client",
        lambda config=None: None,
    )
    result = reflect("W1ABC", "What do you know?")
    assert "not available" in result.lower() or "failed" in result.lower()
