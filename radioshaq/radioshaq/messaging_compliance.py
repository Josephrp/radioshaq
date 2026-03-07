"""Messaging compliance: emergency SMS/WhatsApp region allowlist (Section 9)."""

from __future__ import annotations

from radioshaq.config.schema import EmergencyContactConfig


def emergency_messaging_allowed(region: str, config: EmergencyContactConfig | None) -> bool:
    """
    Return True if emergency SMS/WhatsApp is allowed in the given region.

    Requires config.enabled and region to be in config.regions_allowed.
    Region is typically config.radio.restricted_bands_region (e.g. FCC, CA, CEPT).
    See docs/notify-and-emergency-compliance-plan.md for which regions are supported.
    """
    if config is None or not getattr(config, "enabled", False):
        return False
    regions = getattr(config, "regions_allowed", None) or []
    region_upper = (region or "").strip().upper()
    return region_upper in [r.strip().upper() for r in regions if r]
