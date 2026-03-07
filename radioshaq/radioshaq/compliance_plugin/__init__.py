"""Compliance plugin: registry of region/country backends for restricted bands and band plans."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import ComplianceBackend
from .backends.au import AUBackend
from .backends.ca import CABackend
from .backends.cept import (
    BEBackend,
    CEPTBackend,
    CHBackend,
    ESBackend,
    FRBackend,
    LUBackend,
    MCBackend,
    UKBackend,
)
from .backends.fcc import FCCBackend
from .backends.itu_r1 import ITUR1Backend
from .backends.itu_r3 import ITUR3Backend
from .backends.mx import MXBackend
from .backends.r1_africa import R1AfricaBackend
from .backends.r2_americas import R2AmericasBackend
from .backends.in_ import INBackend
from .backends.jp import JPBackend
from .backends.nz import NZBackend
from .backends.za import ZABackend

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
        if b is not None:
            plans = b.get_band_plans()
            if plans is not None:
                return plans
        return BAND_PLANS
    b = get_backend(restricted_region)
    if b is not None:
        plans = b.get_band_plans()
        if plans is not None:
            return plans
    return BAND_PLANS


# Register built-in backends
register_backend(FCCBackend())
register_backend(CEPTBackend())
register_backend(FRBackend())
register_backend(UKBackend())
register_backend(ESBackend())
register_backend(BEBackend())
register_backend(CHBackend())
register_backend(LUBackend())
register_backend(MCBackend())
register_backend(ITUR1Backend())
register_backend(ITUR3Backend())
register_backend(MXBackend())
register_backend(CABackend())
for _key in ("AR", "CL", "CO", "PE", "VE", "EC", "UY", "PY", "BO", "CR", "PA", "GT", "DO"):
    register_backend(R2AmericasBackend(_key))
register_backend(AUBackend())
# R1 Africa: R1 band plan, no restricted bands in code (verify national rules)
_africa_keys = (
    "ZA", "NG", "KE", "EG", "MA", "TN", "DZ", "GH", "TZ", "ET", "SN", "CI", "CM",
    "BW", "NA", "ZW", "MZ", "UG", "RW", "GA", "ML", "BF", "NE", "TG", "BJ", "CD", "MG",
)
for _key in _africa_keys:
    register_backend(R1AfricaBackend(_key))
register_backend(ZABackend())  # ZA overwrites R1AfricaBackend("ZA") with ICASA list
register_backend(NZBackend())
register_backend(JPBackend())
register_backend(INBackend())

__all__ = [
    "ComplianceBackend",
    "register_backend",
    "get_backend",
    "get_backend_or_default",
    "get_band_plan_source_for_config",
]
