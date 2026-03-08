"""Unit tests for WhatsAppAgent."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from radioshaq.specialized.whatsapp_agent import WhatsAppAgent


@pytest.mark.unit
@pytest.mark.asyncio
async def test_whatsapp_agent_send_success_returns_sid_status() -> None:
    """When Twilio client and from_number are set, send_message returns sid and status."""
    mock_msg = MagicMock()
    mock_msg.sid = "WA123"
    mock_msg.status = "queued"
    client = MagicMock()
    client.messages.create.return_value = mock_msg

    agent = WhatsAppAgent(client=client, from_number="+15551234567")
    result = await agent.execute(
        {"action": "send_message", "to": "+15559876543", "message": "Hello"},
        upstream_callback=None,
    )
    assert result["success"] is True
    assert result["to"] == "+15559876543"
    assert result["sid"] == "WA123"
    assert result["status"] == "queued"
    client.messages.create.assert_called_once()
    call_kw = client.messages.create.call_args[1]
    assert call_kw["body"] == "Hello"
    assert call_kw["from_"] == "whatsapp:+15551234567"
    assert call_kw["to"] == "whatsapp:+15559876543"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_whatsapp_agent_send_not_configured_returns_false() -> None:
    """When client or from_number is missing, returns success False and notes."""
    agent = WhatsAppAgent(client=None, from_number=None)
    result = await agent.execute(
        {"action": "send_message", "to": "+15559876543", "message": "Hi"},
        upstream_callback=None,
    )
    assert result["success"] is False
    assert "not configured" in (result.get("notes") or "").lower() or "missing" in (result.get("notes") or "").lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_whatsapp_agent_receive_returns_placeholder() -> None:
    """Receive action returns success True and notes about channel ingestion."""
    agent = WhatsAppAgent(client=None, from_number=None)
    result = await agent.execute({"action": "receive"}, upstream_callback=None)
    assert result["success"] is True
    assert result.get("action") == "receive"
    assert "receive" in (result.get("notes") or "").lower() or "ingestion" in (result.get("notes") or "").lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_whatsapp_agent_unknown_action_raises() -> None:
    """Unknown action raises ValueError."""
    agent = WhatsAppAgent(client=MagicMock(), from_number="+15551234567")
    with pytest.raises(ValueError, match="Unknown WhatsApp action"):
        await agent.execute({"action": "unknown"}, upstream_callback=None)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_whatsapp_agent_send_empty_to_returns_false() -> None:
    """When to is empty, _do_send returns success False."""
    client = MagicMock()
    agent = WhatsAppAgent(client=client, from_number="+15551234567")
    result = await agent.execute(
        {"action": "send_message", "to": "", "message": "Hi"},
        upstream_callback=None,
    )
    assert result["success"] is False
    assert "to" in result or "required" in (result.get("notes") or "").lower()
    client.messages.create.assert_not_called()
