"""WhatsApp specialized agent (adapt from nanobot)."""

from __future__ import annotations

from typing import Any

from shakods.specialized.base import SpecializedAgent


class WhatsAppAgent(SpecializedAgent):
    """
    Specialized agent for WhatsApp message send/receive.
    Intended to wrap nanobot WhatsApp channel logic when integrated.
    """

    name = "whatsapp"
    description = "Sends and receives messages via WhatsApp"
    capabilities = [
        "whatsapp_send",
        "whatsapp_receive",
    ]

    def __init__(self, client: Any = None):
        """Optional: nanobot WhatsApp client or similar when integrated."""
        self.client = client

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
        """Send a WhatsApp message to a chat/phone."""
        to = task.get("to") or task.get("chat_id") or ""
        message = task.get("message", "")

        await self.emit_progress(upstream_callback, "sending", to=to)

        if not self.client:
            return {
                "success": False,
                "to": to,
                "message_sent": message[:100],
                "notes": "WhatsApp client not configured; integrate nanobot for full support.",
            }

        try:
            # Placeholder: when nanobot is integrated, call client.send(...)
            result = await self._do_send(to, message)
            await self.emit_result(upstream_callback, result)
            return result
        except Exception as e:
            await self.emit_error(upstream_callback, str(e))
            raise

    async def _do_send(self, to: str, message: str) -> dict[str, Any]:
        """Override in integration to use nanobot client."""
        return {
            "success": True,
            "to": to,
            "message_sent": message[:100],
            "notes": "No WhatsApp client configured",
        }
