"""IARU Region 3 band plan (Asia–Pacific). 2m: 144–148 MHz, 70cm: 430–440 MHz.

Source: IARU R3-004 Revised 3 September 2019 (IARU Region 3 Directors' Meeting).
National regulations take precedence; 440–450 MHz is amateur only in Australia and
Philippines per RR 5.270. See https://www.iaru.org/ and IARU R3 band plan PDF.
"""

from __future__ import annotations

from radioshaq.radio.bands import BandPlan

from ..base import ComplianceBackend

# IARU Region 3 band plan. 2m 144–148 MHz (vs R1 144–146); 70cm 430–440 MHz (secondary in R3).
# Other bands aligned with R1/R2 ranges for consistency.
BAND_PLANS_R3: dict[str, BandPlan] = {
    "160m": BandPlan("160m", 1.8e6, 2.0e6, ["CW", "SSB", "DIGITAL"], 1500),
    "80m": BandPlan("80m", 3.5e6, 4.0e6, ["CW", "SSB", "DIGITAL"], 1500),
    "60m": BandPlan("60m", 5.3305e6, 5.4065e6, ["USB", "CW", "DIGITAL"], 100),
    "40m": BandPlan("40m", 7.0e6, 7.3e6, ["CW", "SSB", "DIGITAL"], 1500),
    "30m": BandPlan("30m", 10.1e6, 10.15e6, ["CW", "DIGITAL"], 200),
    "20m": BandPlan("20m", 14.0e6, 14.35e6, ["CW", "SSB", "DIGITAL"], 1500),
    "17m": BandPlan("17m", 18.068e6, 18.168e6, ["CW", "SSB", "DIGITAL"], 1500),
    "15m": BandPlan("15m", 21.0e6, 21.45e6, ["CW", "SSB", "DIGITAL"], 1500),
    "12m": BandPlan("12m", 24.89e6, 24.99e6, ["CW", "SSB", "DIGITAL"], 1500),
    "10m": BandPlan("10m", 28.0e6, 29.7e6, ["CW", "SSB", "FM", "DIGITAL"], 1500),
    "6m": BandPlan("6m", 50.0e6, 54.0e6, ["CW", "SSB", "FM", "DIGITAL"], 1500),
    "2m": BandPlan("2m", 144.0e6, 148.0e6, ["FM", "SSB", "CW", "DIGITAL"], 1500),
    "70cm": BandPlan("70cm", 430.0e6, 440.0e6, ["FM", "SSB", "DIGITAL"], 1500),
}


class ITUR3Backend:
    """Band-plan-only backend for ITU Region 3 (Asia–Pacific). No restricted bands in this backend."""

    region_key: str = "ITU_R3"

    def get_restricted_bands_hz(self) -> list[tuple[float, float]]:
        return []

    def get_band_plans(self) -> dict[str, BandPlan] | None:
        return BAND_PLANS_R3
