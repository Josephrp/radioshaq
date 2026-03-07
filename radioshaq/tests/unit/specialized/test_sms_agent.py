"""Unit tests for SMSAgent."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from radioshaq.specialized.sms_agent import SMSAgent


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sms_agent_send_success_returns_sid_status() -> None:
    """When Twilio client and from_number are set, execute send returns sid and status."""
    mock_msg = MagicMock()
    mock_msg.sid = "SM123"
    mock_msg.status = "queued"
    client = MagicMock()
    client.messages.create.return_value = mock_msg

    agent = SMSAgent(twilio_client=client, from_number="+15551234567")
    result = await agent.execute(
        {"action": "send", "to": "+15559876543", "message": "Hi"},
        upstream_callback=None,
    )
    assert result["success"] is True
    assert result["to"] == "+15559876543"
    assert result["sid"] == "SM123"
    assert result["status"] == "queued"
    client.messages.create.assert_called_once()
    call_kw = client.messages.create.call_args[1]
    assert call_kw["body"] == "Hi"
    assert call_kw["to"] == "+15559876543"
    assert call_kw["from_"] == "+15551234567"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sms_agent_send_missing_to_returns_error() -> None:
    """When to is missing or empty, returns success False and error."""
    agent = SMSAgent(twilio_client=MagicMock(), from_number="+15551234567")
    result = await agent.execute(
        {"action": "send", "message": "Hi"},
        upstream_callback=None,
    )
    assert result["success"] is False
    assert "to" in result or "error" in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sms_agent_send_not_configured_returns_reason() -> None:
    """When twilio_client or from_number is missing, returns success False and reason twilio_not_configured."""
    agent = SMSAgent(twilio_client=None, from_number=None)
    result = await agent.execute(
        {"action": "send", "to": "+15559876543", "message": "Hi"},
        upstream_callback=None,
    )
    assert result["success"] is False
    assert result.get("reason") == "twilio_not_configured"
    assert "not configured" in (result.get("notes") or "")

    agent2 = SMSAgent(twilio_client=MagicMock(), from_number=None)
    result2 = await agent2.execute(
        {"action": "send", "to": "+15559876543", "message": "Hi"},
        upstream_callback=None,
    )
    assert result2["success"] is False
    assert result2.get("reason") == "twilio_not_configured"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sms_agent_receive_returns_placeholder() -> None:
    """Receive action returns success True and notes about webhook."""
    agent = SMSAgent(twilio_client=None, from_number=None)
    result = await agent.execute({"action": "receive"}, upstream_callback=None)
    assert result["success"] is True
    assert result.get("action") == "receive"
    assert "webhook" in (result.get("notes") or "").lower() or "incoming" in (result.get("notes") or "").lower()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sms_agent_e164_normalization() -> None:
    """To and from are normalized to E.164 (e.g. + prefix)."""
    mock_msg = MagicMock()
    mock_msg.sid = "SM456"
    mock_msg.status = "sent"
    client = MagicMock()
    client.messages.create.return_value = mock_msg

    agent = SMSAgent(twilio_client=client, from_number="15551234567")
    result = await agent.execute(
        {"action": "send", "to": "5559876543", "message": "Test"},
        upstream_callback=None,
    )
    assert result["success"] is True
    call_kw = client.messages.create.call_args[1]
    assert call_kw["to"].startswith("+")
    assert call_kw["from_"].startswith("+")
