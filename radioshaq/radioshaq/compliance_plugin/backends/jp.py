"""Japan (ITU R3): MIC/JARL; R3 band plan; conservative restricted set.

No single FCC-style restricted list published; conservative set (aeronautical,
radionav, COSPAS-SARSAT) used. Operator must verify MIC and JARL.
"""

from __future__ import annotations

from radioshaq.radio.bands import BandPlan

from ..base import ComplianceBackend
from .au import RESTRICTED_BANDS_AU_HZ
from .itu_r3 import BAND_PLANS_R3


class JPBackend:
    """
    Japan: ITU Region 3. Restricted bands: conservative set (MIC/JARL);
    R3 band plan. Operator must verify MIC.
    """

    region_key: str = "JP"

    def get_restricted_bands_hz(self) -> list[tuple[float, float]]:
        return RESTRICTED_BANDS_AU_HZ

    def get_band_plans(self) -> dict[str, BandPlan] | None:
        return BAND_PLANS_R3
