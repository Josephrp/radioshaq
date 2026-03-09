"""India (ITU R3): WPC; R3 band plan; conservative restricted set.

WPC (Wireless Planning & Coordination) governs amateur service; restricted
licence 144–146 MHz, 434–438 MHz. Conservative restricted set used.
Operator must verify WPC and ARSI.
"""

from __future__ import annotations

from radioshaq.radio.bands import BandPlan

from ..base import ComplianceBackend
from .au import RESTRICTED_BANDS_AU_HZ
from .itu_r3 import BAND_PLANS_R3


class INBackend:
    """
    India: ITU Region 3. Restricted bands: conservative set (WPC);
    R3 band plan. Operator must verify WPC.
    """

    region_key: str = "IN"

    def get_restricted_bands_hz(self) -> list[tuple[float, float]]:
        return RESTRICTED_BANDS_AU_HZ

    def get_band_plans(self) -> dict[str, BandPlan] | None:
        return BAND_PLANS_R3
