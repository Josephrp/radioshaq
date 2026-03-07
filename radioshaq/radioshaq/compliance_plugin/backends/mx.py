"""Mexico (ITU R2): restricted bands baseline from FCC §15.205; R2 band plan.

IFT CNAF (Cuadro Nacional de Atribución de Frecuencias) and IFT-016-2024
(30 MHz–3 GHz low-power devices) apply; FCC used as baseline. Verify IFT for
national differences.
"""

from __future__ import annotations

from radioshaq.radio.bands import BandPlan

from ..base import ComplianceBackend
from .fcc import RESTRICTED_BANDS_FCC_HZ


class MXBackend:
    """
    Mexico: ITU Region 2. Restricted bands: FCC §15.205 baseline (IFT CNAF,
    IFT-016-2024). Band plan: default R2. Operator must verify IFT.
    """

    region_key: str = "MX"

    def get_restricted_bands_hz(self) -> list[tuple[float, float]]:
        return RESTRICTED_BANDS_FCC_HZ

    def get_band_plans(self) -> dict[str, BandPlan] | None:
        return None
