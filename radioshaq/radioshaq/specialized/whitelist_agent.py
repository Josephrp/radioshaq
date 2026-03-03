"""Whitelist specialized agent: evaluate whitelist requests and optionally register callsigns for gated access."""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger

from radioshaq.specialized.base import SpecializedAgent

# Callsign: 3–7 letters/numbers, optional -digit (SSID)
CALLSIGN_PATTERN = re.compile(r"^[A-Z0-9]{3,7}(-[0-9]{1,2})?$", re.IGNORECASE)


class WhitelistAgent(SpecializedAgent):
    """
    Evaluates whitelist requests (LLM): approve/deny access to gated services (e.g. passing
    messages between bands). Optionally registers the callsign, returns a short message for the user (e.g. for TTS).
    """

    name = "whitelist"
    description = "Evaluates whitelist requests and registers approved callsigns for gated services (messaging between bands, etc.)"
    capabilities = ["whitelist", "whitelist_evaluation"]

    def __init__(
        self,
        repository: Any = None,
        llm_client: Any = None,
        eval_prompt: str | None = None,
    ) -> None:
        self.repository = repository
        self.llm_client = llm_client
        self.eval_prompt = eval_prompt or (
            "You evaluate whitelist requests for access to gated services (e.g. passing messages between bands). "
            "Reply with JSON only: "
            '{"approved": bool, "reason": "short sentence", "callsign": "K5ABC or null"}'
        )

    async def execute(
        self,
        task: dict[str, Any],
        upstream_callback: Any = None,
    ) -> dict[str, Any]:
        request_text = (
            task.get("request_text")
            or task.get("description")
            or task.get("message")
            or ""
        ).strip()
        stated_callsign = (task.get("callsign") or "").strip() or None

        if not request_text:
            return {
                "approved": False,
                "reason": "No request text provided.",
                "callsign_registered": None,
                "message_for_user": "No request received. Please state why you need access to gated services (e.g. messaging between bands).",
            }

        if self.repository is None:
            return {
                "approved": False,
                "reason": "Registry not available.",
                "error": "no_repository",
                "callsign_registered": None,
                "message_for_user": "Registration is not available right now.",
            }

        if self.llm_client is None:
            return {
                "approved": False,
                "reason": "Evaluation service not available.",
                "callsign_registered": None,
                "message_for_user": "Evaluation is not available right now.",
            }

        await self.emit_progress(upstream_callback, "evaluating", request_preview=request_text[:100])

        user_message = request_text
        if stated_callsign:
            user_message = f"{request_text}\n\nStated callsign: {stated_callsign}."

        try:
            response = await self.llm_client.chat(
                messages=[
                    {"role": "system", "content": self.eval_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.2,
                max_tokens=512,
            )
            content = (response.content or "").strip()
        except Exception as e:
            logger.exception("Whitelist LLM call failed: %s", e)
            return {
                "approved": False,
                "reason": "Evaluation failed.",
                "callsign_registered": None,
                "message_for_user": "We couldn't process your request. Please try again.",
            }

        approved = False
        reason = "Unable to evaluate."
        callsign_from_llm = None

        try:
            # Strip possible markdown code fences
            if "```" in content:
                for part in content.split("```"):
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    if part.startswith("{"):
                        content = part
                        break
            data = json.loads(content)
            approved = bool(data.get("approved", False))
            reason = str(data.get("reason", reason))
            raw_callsign = data.get("callsign")
            if raw_callsign and isinstance(raw_callsign, str):
                callsign_from_llm = raw_callsign.strip().upper()
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Whitelist LLM response not valid JSON: %s", e)
            reason = "Evaluation could not be parsed."

        callsign_to_register = stated_callsign or callsign_from_llm
        if callsign_to_register:
            callsign_to_register = callsign_to_register.strip().upper()
        if callsign_to_register and not CALLSIGN_PATTERN.match(callsign_to_register):
            callsign_to_register = None

        callsign_registered = None
        if approved and callsign_to_register:
            try:
                await self.repository.register(callsign_to_register, source="whitelist")
                callsign_registered = callsign_to_register
            except Exception as e:
                logger.warning("Whitelist register failed: %s", e)
                reason = f"{reason} Registration failed."
                callsign_registered = None

        if approved:
            if callsign_registered:
                message_for_user = f"You're approved and whitelisted as {callsign_registered}. You can use gated services like messaging between bands."
            else:
                message_for_user = f"Approved. {reason}" if reason else "You're approved."
        else:
            message_for_user = f"Not approved. {reason}" if reason else "Not approved."

        result = {
            "approved": approved,
            "reason": reason,
            "callsign_registered": callsign_registered,
            "message_for_user": message_for_user,
        }
        await self.emit_result(upstream_callback, result)
        return result
