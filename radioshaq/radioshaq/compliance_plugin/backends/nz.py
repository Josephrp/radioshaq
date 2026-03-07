"""New Zealand (ITU R3): RSM PIB 21 conservative restricted bands + R3 band plan.

Restricted bands from RSM (Radio Spectrum Management) Table of Radio Spectrum
Usage (PIB 21) and prohibited equipment rules; conservative set (aeronautical,
radionav, COSPAS-SARSAT, etc.). Operator must verify RSM.
"""

from __future__ import annotations

from radioshaq.radio.bands import BandPlan

from ..base import ComplianceBackend
from .au import RESTRICTED_BANDS_AU_HZ
from .itu_r3 import BAND_PLANS_R3


class NZBackend:
    """
    New Zealand: ITU Region 3. Restricted bands: RSM PIB 21 conservative set;
    R3 band plan. Operator must verify RSM.
    """

    region_key: str = "NZ"

    def get_restricted_bands_hz(self) -> list[tuple[float, float]]:
        return RESTRICTED_BANDS_AU_HZ  # Same conservative set (ITU-aligned)

    def get_band_plans(self) -> dict[str, BandPlan] | None:
        return BAND_PLANS_R3
