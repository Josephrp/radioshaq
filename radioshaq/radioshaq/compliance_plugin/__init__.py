"""Compliance plugin: registry of region/country backends for restricted bands and band plans."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import ComplianceBackend
from .backends.cept import CEPTBackend, FRBackend
from .backends.fcc import FCCBackend
from .backends.itu_r1 import ITUR1Backend

if TYPE_CHECKING:
    from radioshaq.radio.bands import BandPlan

_backends: dict[str, ComplianceBackend] = {}


def register_backend(backend: ComplianceBackend) -> None:
    _backends[backend.region_key] = backend


def get_backend(region_key: str) -> ComplianceBackend | None:
    return _backends.get(region_key)


def get_backend_or_default(region_key: str, default: ComplianceBackend) -> ComplianceBackend:
    return _backends.get(region_key) or default


def get_band_plan_source_for_config(
    restricted_region: str,
    band_plan_region: str | None,
) -> dict[str, "BandPlan"]:
    """Effective band plan for allowlist and /radio/bands. Uses band_plan_region override if set."""
    from radioshaq.radio.bands import BAND_PLANS

    if band_plan_region is not None and str(band_plan_region).strip():
        b = get_backend(str(band_plan_region).strip())
        if b is not None and b.get_band_plans() is not None:
            return b.get_band_plans()
        return BAND_PLANS
    b = get_backend(restricted_region)
    if b is not None and b.get_band_plans() is not None:
        return b.get_band_plans()
    return BAND_PLANS


# Register built-in backends
register_backend(FCCBackend())
register_backend(CEPTBackend())
register_backend(FRBackend())
register_backend(ITUR1Backend())

__all__ = [
    "ComplianceBackend",
    "register_backend",
    "get_backend",
    "get_backend_or_default",
    "get_band_plan_source_for_config",
]
