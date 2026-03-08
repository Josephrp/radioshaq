"""ITU Region 1 Africa: IARU R1 band plan + R1 conservative restricted bands.

African countries are in ITU Region 1. Restricted bands: R1 conservative set
(safety/aeronautical/marine/COSPAS-SARSAT); national rules may add. ZA uses
dedicated ZABackend (ICASA list). Operators must verify national regulator
(ICASA, NCC, CA, NTRA, ANRT, BOCRA, etc.).
Reference: IARU R1 https://www.iaru-r1.org/on-the-air/band-plans/
"""

from __future__ import annotations

from radioshaq.radio.bands import BandPlan

from ..base import ComplianceBackend
from .cept import RESTRICTED_BANDS_CEPT_HZ
from .itu_r1 import BAND_PLANS_R1


class R1AfricaBackend:
    """
    Parametrised backend for ITU R1 African countries: R1 band plan and
    R1 conservative restricted bands (CEPT-aligned; ZA overridden by ZABackend).
    """

    def __init__(self, region_key: str) -> None:
        self.region_key = region_key

    def get_restricted_bands_hz(self) -> list[tuple[float, float]]:
        return RESTRICTED_BANDS_CEPT_HZ

    def get_band_plans(self) -> dict[str, BandPlan] | None:
        return BAND_PLANS_R1
