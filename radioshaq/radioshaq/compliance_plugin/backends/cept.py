"""CEPT/EU harmonised restricted bands and R1 band plan.

Regulatory sources (intentional radiation / protected bands):
- ERC/REC 70-03 (Short Range Devices): https://docdb.cept.org/document/845 — Annexes define
  allowed SRD bands; Appendix 3 lists national restrictions. EFIS: https://efis.cept.org/
- EU Commission Decision 2006/771/EC (as amended): harmonised SRD spectrum; annex lists
  allowed bands and conditions. EUR-Lex CELEX 32006D0771.
- ETSI EN 300 220: permitted SRD bands 25–1000 MHz (e.g. 433.04–434.79, 863–876, 915–921 MHz).
  Restricted = bands not in harmonised SRD/amateur allocations; safety (aeronautical, COSPAS-SARSAT,
  marine) protected. National (e.g. ANFR France) may add further restrictions.
"""

from __future__ import annotations

from radioshaq.radio.bands import BandPlan

from ..base import ComplianceBackend
from .itu_r1 import BAND_PLANS_R1

# CEPT/EU restricted bands derived from ECC/ETSI harmonised framework (ERC/REC 70-03,
# EU Decision 2006/771/EC as amended, ETSI EN 300 220). This list does NOT mirror FCC §15.205:
# - FCC-only ranges (e.g. 240–285 MHz, 322–335.4 MHz, US GHz blocks) are omitted.
# - EU may restrict additional ISM/SRD sub-bands; national implementations (e.g. ANFR) may add more.
# Operator must verify national rules. Reference: https://efis.cept.org/
RESTRICTED_BANDS_CEPT_HZ: list[tuple[float, float]] = [
    # Aeronautical, radionavigation, safety
    (0.090e6, 0.110e6),
    (0.495e6, 0.505e6),
    (2.1735e6, 2.1905e6),
    (4.125e6, 4.128e6),
    (4.17725e6, 4.17775e6),
    (4.20725e6, 4.20775e6),
    (6.215e6, 6.218e6),
    (6.26775e6, 6.26825e6),
    (6.31175e6, 6.31225e6),
    (8.291e6, 8.294e6),
    (8.362e6, 8.366e6),
    (8.37625e6, 8.38675e6),
    (8.41425e6, 8.41475e6),
    (12.29e6, 12.293e6),
    (12.51975e6, 12.52025e6),
    (12.57675e6, 12.57725e6),
    (13.36e6, 13.41e6),
    (16.42e6, 16.423e6),
    (16.69475e6, 16.69525e6),
    (16.80425e6, 16.80475e6),
    (25.5e6, 25.67e6),
    (37.5e6, 38.25e6),
    (73e6, 74.6e6),
    (74.8e6, 75.2e6),
    (108e6, 121.94e6),  # Aeronautical
    (123e6, 138e6),
    (149.9e6, 150.05e6),
    (156.52475e6, 156.52525e6),
    (156.7e6, 156.9e6),  # Marine mobile
    (162.0125e6, 167.17e6),
    (167.72e6, 173.2e6),
    (399.9e6, 410e6),  # COSPAS-SARSAT (406.0–406.1) and adjacent
    (608e6, 614e6),
    (960e6, 1240e6),
    (1300e6, 1427e6),
    (1435e6, 1626.5e6),
    (1645.5e6, 1646.5e6),
    (1660e6, 1710e6),
    (1718.8e6, 1722.2e6),
    (2200e6, 2300e6),
    (2310e6, 2390e6),
    (2483.5e6, 2500e6),
    (2690e6, 2900e6),
    (3260e6, 3267e6),
    (3332e6, 3339e6),
    (3345.8e6, 3358e6),
    (3600e6, 4400e6),
    # No US-specific GHz blocks (4.5–5.15, 5.35–5.46, 7.25–7.75, 8.025–8.5, 9–9.2, 9.3–9.5,
    # 10.6–12.7, 13.25–13.4, 14.47–14.5, 15.35–16.2, 17.7–21.4, 22.01–23.12, 23.6–24,
    # 31.2–31.8, 36.43–36.5, 38.6–100 GHz) — CEPT allocations differ; add per ECC if needed.
]


class CEPTBackend:
    """CEPT/EU restricted bands + IARU R1 band plan (for France, Spain, etc.)."""

    region_key: str = "CEPT"

    def get_restricted_bands_hz(self) -> list[tuple[float, float]]:
        return RESTRICTED_BANDS_CEPT_HZ

    def get_band_plans(self) -> dict[str, BandPlan] | None:
        return BAND_PLANS_R1


class FRBackend(CEPTBackend):
    """France: same as CEPT (EU harmonised + R1 band plan)."""

    region_key: str = "FR"


class UKBackend(CEPTBackend):
    """United Kingdom: CEPT-aligned (Ofcom); R1 band plan."""

    region_key: str = "UK"


class ESBackend(CEPTBackend):
    """Spain: CEPT (EU) + IARU R1 band plan."""

    region_key: str = "ES"


class BEBackend(CEPTBackend):
    """Belgium: CEPT (TR 61-01/61-02) + IARU R1 band plan."""

    region_key: str = "BE"


class CHBackend(CEPTBackend):
    """Switzerland: CEPT + IARU R1 band plan."""

    region_key: str = "CH"


class LUBackend(CEPTBackend):
    """Luxembourg: CEPT + IARU R1 band plan."""

    region_key: str = "LU"


class MCBackend(CEPTBackend):
    """Monaco: CEPT + IARU R1 band plan."""

    region_key: str = "MC"
