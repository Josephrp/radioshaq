"""Canada (ITU R2): FCC §15.205 baseline + R2 band plan.

Restricted bands per ISED RSS-210 Section 7.1 and Annexes A/B (restricted
frequency bands); aligned with FCC §15.205 unless ISED publishes differences.
Amateur radio: RBR-4. Canada participates in CEPT T/R 61-01 for reciprocal
operation in Europe; for domestic compliance this backend uses FCC baseline.
"""

from __future__ import annotations

from radioshaq.radio.bands import BandPlan

from ..base import ComplianceBackend
from .fcc import RESTRICTED_BANDS_FCC_HZ


class CABackend:
    """
    Canada: ITU Region 2. Restricted bands: RSS-210 §7.1 and Annexes A/B;
    FCC §15.205 used as baseline. Band plan: default R2. Operator must verify ISED.
    """

    region_key: str = "CA"

    def get_restricted_bands_hz(self) -> list[tuple[float, float]]:
        return RESTRICTED_BANDS_FCC_HZ

    def get_band_plans(self) -> dict[str, BandPlan] | None:
        return None
