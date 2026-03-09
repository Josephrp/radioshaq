"""SMS specialized agent (Twilio integration). Twilio expects E.164 for phone numbers."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from radioshaq.constants import E164_PATTERN
from radioshaq.specialized.base import SpecializedAgent
from radioshaq.utils.phone import normalize_e164


class SMSAgent(SpecializedAgent):
    """
    Specialized agent for SMS send/receive via Twilio.
    """

    name = "sms"
    description = "Sends and receives SMS via Twilio"
    capabilities = [
        "sms_send",
        "sms_receive",
    ]

    def __init__(self, twilio_client: Any = None, from_number: str | None = None):
        """Optional: Twilio REST client and from phone number."""
        self.twilio_client = twilio_client
        self.from_number = from_number

    async def execute(
        self,
        task: dict[str, Any],
        upstream_callback: Any = None,
    ) -> dict[str, Any]:
        """Execute SMS task: send, or receive placeholder."""
        action = task.get("action", "send")

        if action == "send":
            return await self._send(task, upstream_callback)
        if action == "receive":
            return {
                "success": True,
                "action": "receive",
                "notes": "Incoming SMS handled by webhook; use orchestrator for incoming.",
            }
        raise ValueError(f"Unknown SMS action: {action}")

    async def _send(
        self, task: dict[str, Any], upstream_callback: Any
    ) -> dict[str, Any]:
        """Send SMS via Twilio. Phone numbers are normalized to E.164."""
        to = normalize_e164(task.get("to") or "")
        body = task.get("message", "") or task.get("body", "")

        await self.emit_progress(upstream_callback, "sending", to=to)

        if not to:
            return {"success": False, "error": "to (phone number) is required"}
        if not E164_PATTERN.match(to):
            return {
                "success": False,
                "error": "to must be E.164 (10–15 digits)",
                "to": to,
                "reason": "invalid_e164",
            }
        if not self.twilio_client or not self.from_number:
            return {
                "success": False,
                "to": to,
                "notes": "Twilio client or from_number not configured",
                "reason": "twilio_not_configured",
            }
        from_e164 = normalize_e164(self.from_number)
        if not from_e164:
            return {
                "success": False,
                "to": to,
                "notes": "from_number normalizes to empty string; check Twilio sender config",
                "reason": "invalid_from",
            }

        try:
            msg = await asyncio.to_thread(
                self.twilio_client.messages.create,
                body=body,
                from_=from_e164,
                to=to,
            )
            result = {
                "success": True,
                "to": to,
                "sid": msg.sid,
                "status": getattr(msg, "status", None),
            }
            await self.emit_result(upstream_callback, result)
            return result
        except Exception as e:
            logger.exception("SMS send failed: %s", e)
            await self.emit_error(upstream_callback, str(e))
            raise
