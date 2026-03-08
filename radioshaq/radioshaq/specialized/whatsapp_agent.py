"""WhatsApp specialized agent (Twilio WhatsApp Business API)."""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from radioshaq.specialized.base import SpecializedAgent
from radioshaq.utils.phone import normalize_e164


class WhatsAppAgent(SpecializedAgent):
    """
    Specialized agent for WhatsApp message send/receive via Twilio.
    Uses same Twilio client as SMS with from_/to as whatsapp:+E.164.
    """

    name = "whatsapp"
    description = "Sends and receives messages via WhatsApp (Twilio)"
    capabilities = [
        "whatsapp_send",
        "whatsapp_receive",
    ]

    def __init__(self, client: Any = None, from_number: str | None = None):
        """Twilio REST client and WhatsApp sender number (E.164); both required for send."""
        self.client = client
        self.from_number = from_number

    async def execute(
        self,
        task: dict[str, Any],
        upstream_callback: Any = None,
    ) -> dict[str, Any]:
        """Execute WhatsApp task: send_message, or return receive placeholder."""
        action = task.get("action", "send_message")

        if action == "send_message":
            return await self._send_message(task, upstream_callback)
        if action == "receive":
            return {
                "success": True,
                "action": "receive",
                "notes": "Receive is handled by channel ingestion; use orchestrator for incoming messages.",
            }
        raise ValueError(f"Unknown WhatsApp action: {action}")

    async def _send_message(
        self, task: dict[str, Any], upstream_callback: Any
    ) -> dict[str, Any]:
        """Send a WhatsApp message to a chat/phone (E.164)."""
        to = task.get("to") or task.get("chat_id") or ""
        message = task.get("message", "")

        await self.emit_progress(upstream_callback, "sending", to=to)

        if not self.client or not self.from_number:
            return {
                "success": False,
                "to": to,
                "message_sent": (message or "")[:100],
                "notes": "Twilio WhatsApp not configured (client or whatsapp_from missing).",
            }

        try:
            result = await self._do_send(to, message)
            await self.emit_result(upstream_callback, result)
            return result
        except Exception as e:
            logger.exception("WhatsApp send failed: %s", e)
            await self.emit_error(upstream_callback, str(e))
            raise

    async def _do_send(self, to: str, message: str) -> dict[str, Any]:
        """Send via Twilio WhatsApp: from_ and to use whatsapp:+E.164."""
        to_e164 = normalize_e164(to)
        from_e164 = normalize_e164(self.from_number)
        if not to_e164:
            return {
                "success": False,
                "to": to,
                "notes": "to (phone number) is required",
            }
        try:
            msg = await asyncio.to_thread(
                self.client.messages.create,
                body=message or "",
                from_="whatsapp:" + from_e164,
                to="whatsapp:" + to_e164,
            )
            return {
                "success": True,
                "to": to_e164,
                "sid": msg.sid,
                "status": getattr(msg, "status", None),
                "message_sent": (message or "")[:100],
            }
        except Exception as e:
            logger.exception("WhatsApp _do_send failed: %s", e)
            raise
