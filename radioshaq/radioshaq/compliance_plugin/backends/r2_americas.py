"""ITU Region 2 Americas: FCC §15.205 baseline + default R2 band plan.

Many Latin American and Caribbean countries follow FCC-style restricted bands
and IARU R2 band plan. National regulators (e.g. ENACOM Argentina, SUBTEL Chile,
CRC Colombia, MTC Peru) may vary; operators must verify local rules.
Reference: IARU R2 band plan https://www.iaru-r2.org/en/reference/band-plans/
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..base import ComplianceBackend
from .fcc import RESTRICTED_BANDS_FCC_HZ

if TYPE_CHECKING:
    from radioshaq.radio.bands import BandPlan


class R2AmericasBackend:
    """
    Parametrised backend for ITU R2 Americas: FCC §15.205 restricted bands,
    default R2 band plan (bands.py). Use for Argentina, Chile, Colombia, etc.
    """

    def __init__(self, region_key: str) -> None:
        self.region_key = region_key

    def get_restricted_bands_hz(self) -> list[tuple[float, float]]:
        return RESTRICTED_BANDS_FCC_HZ

    def get_band_plans(self) -> dict[str, "BandPlan"] | None:
        return None
