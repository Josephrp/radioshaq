"""Whitelist tools for orchestrator (LLM-callable): list registered callsigns, register callsign for gated access."""

from __future__ import annotations

import json
import re
from typing import Any

from radioshaq.callsign.repository import CallsignRegistryRepository

# Callsign: 3–7 letters/numbers, optional -digit (SSID)
CALLSIGN_PATTERN = re.compile(r"^[A-Z0-9]{3,7}(-[0-9]{1,2})?$", re.IGNORECASE)


class ListRegisteredCallsignsTool:
    """Tool: list all currently whitelisted (registered) callsigns with access to gated services."""

    name = "list_registered_callsigns"
    description = "List all currently whitelisted callsigns (registered for gated services such as messaging between bands)."

    def __init__(self, repository: CallsignRegistryRepository | None = None) -> None:
        self.repository = repository

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Optional maximum number of callsigns to return.",
                        },
                    },
                    "required": [],
                },
            },
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        if "limit" in params and params["limit"] is not None:
            if not isinstance(params["limit"], int) or params["limit"] < 1:
                return ["limit must be a positive integer"]
        return []

    async def execute(self, limit: int | None = None, **kwargs: Any) -> str:
        if self.repository is None:
            return "Error: Registry not available."
        registered = await self.repository.list_registered()
        if limit is not None and limit > 0:
            registered = registered[:limit]
        # Include preferred_bands and last_band for each callsign (relay planning)
        out = [
            {
                "callsign": r.get("callsign", r),
                "last_band": r.get("last_band"),
                "preferred_bands": r.get("preferred_bands") or [],
            }
            for r in registered
        ]
        return json.dumps({"registered": out, "count": len(out)})


class RegisterCallsignTool:
    """Tool: whitelist a callsign so they can use gated services (e.g. passing messages between bands)."""

    name = "register_callsign"
    description = "Whitelist a callsign so they are accepted for gated services (messaging between bands, etc.)."

    def __init__(self, repository: CallsignRegistryRepository | None = None) -> None:
        self.repository = repository

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "callsign": {
                            "type": "string",
                            "description": "Callsign to whitelist (3–7 alphanumeric, optional -digit e.g. K5ABC or W1XYZ-1)",
                        },
                        "source": {
                            "type": "string",
                            "description": "Source of registration",
                            "default": "api",
                        },
                    },
                    "required": ["callsign"],
                },
            },
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors = []
        callsign = params.get("callsign")
        if not callsign or not isinstance(callsign, str):
            errors.append("callsign is required")
        else:
            normalized = callsign.strip().upper()
            if not CALLSIGN_PATTERN.match(normalized):
                errors.append("callsign must be 3–7 alphanumeric chars, optional -digit (e.g. K5ABC or W1XYZ-1)")
        return errors

    async def execute(
        self,
        callsign: str,
        source: str = "api",
        **kwargs: Any,
    ) -> str:
        if self.repository is None:
            return "Error: Registry not available."
        normalized = callsign.strip().upper()
        try:
            row_id = await self.repository.register(normalized, source=source)
            return f"Registered {normalized} (id={row_id})"
        except ValueError as e:
            return f"Error: {e}"
