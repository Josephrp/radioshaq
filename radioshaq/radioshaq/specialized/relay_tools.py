"""Relay tool for orchestrator: relay a message from one band to another (LLM-callable)."""

from __future__ import annotations

import re
from typing import Any

from radioshaq.compliance_plugin import get_band_plan_source_for_config
from radioshaq.constants import E164_PATTERN
from radioshaq.radio.bands import BAND_PLANS
from radioshaq.relay.service import relay_message_between_bands_service
from radioshaq.utils.phone import normalize_e164

# Optional ISO datetime for deliver_at (lenient)
DELIVER_AT_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$"
)


class RelayMessageTool:
    """Tool: relay a message from one band to another. Store for recipient to poll; no broadcast unless site config enables it."""

    name = "relay_message_between_bands"
    description = (
        "Relay a message from one band to another, or to SMS/WhatsApp. "
        "For radio: stores the message so the destination callsign can poll (GET /transcripts?callsign=<dest>&destination_only=true&band=<target_band>). "
        "For sms/whatsapp: set target_channel to 'sms' or 'whatsapp' and destination_phone (E.164); message is delivered via Twilio. "
        "Does not broadcast or transmit unless site config enables it. "
        "Use when the user or a radio contact asks to pass a message to another band, callsign, or phone."
    )

    def __init__(
        self,
        storage: Any = None,
        injection_queue: Any = None,
        get_radio_tx: Any = None,
        config: Any = None,
        callsign_repository: Any = None,
        message_bus: Any = None,
    ) -> None:
        self._storage = storage
        self._injection_queue = injection_queue
        self._get_radio_tx = get_radio_tx
        self._config = config
        self._callsign_repository = callsign_repository
        self._message_bus = message_bus

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {
                            "type": "string",
                            "description": "The message text to relay.",
                        },
                        "source_band": {
                            "type": "string",
                            "description": "Band where the message originated (e.g. 40m, 2m).",
                        },
                        "target_band": {
                            "type": "string",
                            "description": "Band to deliver the message to (e.g. 2m, 40m). Required for radio; omit or use placeholder for sms/whatsapp.",
                        },
                        "source_callsign": {
                            "type": "string",
                            "description": "Callsign of the sender.",
                            "default": "UNKNOWN",
                        },
                        "destination_callsign": {
                            "type": "string",
                            "description": "Callsign of the recipient (optional).",
                        },
                        "source_frequency_hz": {
                            "type": "number",
                            "description": "Source frequency in Hz (optional).",
                        },
                        "target_frequency_hz": {
                            "type": "number",
                            "description": "Target frequency in Hz (optional).",
                        },
                        "deliver_at": {
                            "type": "string",
                            "description": "ISO datetime for scheduled delivery (optional).",
                        },
                        "target_channel": {
                            "type": "string",
                            "description": "Delivery channel: 'radio' (default), 'sms', or 'whatsapp'. If sms/whatsapp, destination_phone is required.",
                            "default": "radio",
                        },
                        "destination_phone": {
                            "type": "string",
                            "description": "E.164 phone number for SMS/WhatsApp delivery when target_channel is sms or whatsapp.",
                        },
                        "emergency": {
                            "type": "boolean",
                            "description": "If true and target_channel is sms/whatsapp, message is queued for human approval (emergency contact flow). Only allowed when emergency_contact is enabled for this region.",
                            "default": False,
                        },
                    },
                    "required": ["message", "source_band"],
                },
            },
        }

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not params.get("message") or not isinstance(params.get("message"), str):
            errors.append("message is required")
        if not params.get("source_band") or not isinstance(params.get("source_band"), str):
            errors.append("source_band is required")
        source_band = (params.get("source_band") or "").strip()
        target_band = (params.get("target_band") or "").strip()
        target_channel = (params.get("target_channel") or "radio").strip().lower()
        if target_channel == "radio" and (not target_band or not isinstance(params.get("target_band"), str)):
            errors.append("target_band is required when target_channel is radio")
        destination_phone = (params.get("destination_phone") or "").strip()
        if target_channel not in ("radio", "sms", "whatsapp"):
            errors.append("target_channel must be radio, sms, or whatsapp")
        if target_channel in ("sms", "whatsapp") and not destination_phone:
            errors.append("destination_phone is required when target_channel is sms or whatsapp")
        if target_channel in ("sms", "whatsapp") and destination_phone:
            normalised = normalize_e164(destination_phone)
            if not E164_PATTERN.match(normalised):
                errors.append(
                    f"destination_phone must be E.164 (e.g. +14155552671); got: {destination_phone!r}"
                )
        if params.get("emergency") is True and target_channel not in ("sms", "whatsapp"):
            errors.append("emergency only applies when target_channel is sms or whatsapp")
        config = self._config
        radio = getattr(config, "radio", None) if config else None
        if not radio:
            radio = config
        if radio:
            band_plans = get_band_plan_source_for_config(
                getattr(radio, "restricted_bands_region", "FCC"),
                getattr(radio, "band_plan_region", None),
            )
        else:
            band_plans = BAND_PLANS
        if source_band and source_band not in band_plans:
            errors.append(f"Unknown source_band: {source_band}; use e.g. 40m, 2m, 20m")
        if target_channel == "radio" and target_band and target_band not in band_plans:
            errors.append(f"Unknown target_band: {target_band}; use e.g. 40m, 2m, 20m")
        if params.get("source_frequency_hz") is not None and not isinstance(
            params.get("source_frequency_hz"), (int, float)
        ):
            errors.append("source_frequency_hz must be a number")
        if params.get("target_frequency_hz") is not None and not isinstance(
            params.get("target_frequency_hz"), (int, float)
        ):
            errors.append("target_frequency_hz must be a number")
        deliver_at = params.get("deliver_at")
        if deliver_at is not None and isinstance(deliver_at, str) and deliver_at.strip():
            if not DELIVER_AT_PATTERN.match(deliver_at.strip()):
                errors.append("deliver_at must be an ISO datetime string (e.g. 2026-12-01T12:00:00Z)")
        return errors

    async def execute(
        self,
        message: str,
        source_band: str,
        target_band: str,
        source_callsign: str = "UNKNOWN",
        destination_callsign: str | None = None,
        source_frequency_hz: float | None = None,
        target_frequency_hz: float | None = None,
        deliver_at: str | None = None,
        target_channel: str = "radio",
        destination_phone: str | None = None,
        emergency: bool = False,
        **kwargs: Any,
    ) -> str:
        if self._storage is None or getattr(self._storage, "db", None) is None:
            return "Error: Relay not available (no storage)."

        config = self._config
        radio_cfg = getattr(config, "radio", None) if config else None
        if not radio_cfg:
            radio_cfg = config
        if (
            radio_cfg
            and getattr(radio_cfg, "callsign_registry_required", False)
            and self._callsign_repository is not None
        ):
            allowed: set[str] = set()
            if getattr(radio_cfg, "allowed_callsigns", None):
                allowed = {
                    c.strip().upper()
                    for c in radio_cfg.allowed_callsigns
                    if c and isinstance(c, str)
                }
            try:
                for r in await self._callsign_repository.list_registered():
                    cs = r.get("callsign")
                    if cs:
                        allowed.add(str(cs).strip().upper())
            except Exception:
                pass
            from radioshaq.api.callsign_whitelist import is_callsign_allowed

            if not is_callsign_allowed(
                source_callsign, allowed, getattr(radio_cfg, "callsign_registry_required", False)
            ):
                return "Error: Source callsign not allowed."
            if destination_callsign and not is_callsign_allowed(
                destination_callsign, allowed, getattr(radio_cfg, "callsign_registry_required", False)
            ):
                return "Error: Destination callsign not allowed."

        tx_agent = None
        if callable(self._get_radio_tx):
            tx_agent = self._get_radio_tx()

        result = await relay_message_between_bands_service(
            message=message,
            source_band=source_band.strip(),
            target_band=target_band.strip() if (target_channel or "radio") == "radio" else (target_channel or "radio"),
            source_frequency_hz=source_frequency_hz,
            target_frequency_hz=target_frequency_hz,
            source_callsign=source_callsign or "UNKNOWN",
            destination_callsign=destination_callsign,
            deliver_at=deliver_at.strip() if isinstance(deliver_at, str) and deliver_at.strip() else None,
            storage=self._storage,
            injection_queue=self._injection_queue,
            radio_tx_agent=tx_agent,
            config=config,
            store_only_relayed=getattr(radio_cfg, "relay_store_only_relayed", False),
            target_channel=(target_channel or "radio").strip().lower(),
            destination_phone=(destination_phone or "").strip() or None,
            emergency=emergency,
            message_bus=self._message_bus,
        )

        if not result.get("ok"):
            return f"Error: {result.get('error', 'relay failed')}"

        if result.get("queued_for_approval"):
            return (
                f"Emergency relay queued for human approval (event_id={result.get('event_id')}). "
                "An operator must approve via POST /emergency/events/{id}/approve before the message is sent."
            )

        if result.get("relay") == "no_storage":
            return (
                "Relay accepted (no DB to store). "
                f"Source band: {result.get('source_band')}, target band: {result.get('target_band')}."
            )

        sid = result.get("source_transcript_id")
        rid = result.get("relayed_transcript_id")
        dest = result.get("target_band")
        dest_cs = destination_callsign or "recipient"
        tch = (target_channel or "radio").strip().lower()
        if tch in ("sms", "whatsapp"):
            return (
                f"Relayed to {tch}. Source transcript ID: {sid}, relayed ID: {rid}. "
                f"Message will be delivered via {tch} (relay_delivery worker + outbound handler)."
            )
        return (
            f"Relayed. Source transcript ID: {sid}, relayed ID: {rid}. "
            f"Recipient can poll GET /transcripts?callsign={dest_cs}&destination_only=true&band={dest}."
        )
