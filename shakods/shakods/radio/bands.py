"""Band plans and frequency allocations for ham radio."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BandPlan:
    """Band plan for a ham radio band."""

    name: str
    freq_start_hz: float
    freq_end_hz: float
    modes: list[str]
    power_limit_w: float | None = None
    license_class: str | None = None


# ITU Region 2 (Americas) band plans - simplified
BAND_PLANS: dict[str, BandPlan] = {
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
    "70cm": BandPlan("70cm", 420.0e6, 450.0e6, ["FM", "SSB", "DIGITAL"], 1500),
}


def get_band_for_frequency(freq_hz: float) -> str | None:
    """Return band name for a frequency, or None if out of band."""
    for name, plan in BAND_PLANS.items():
        if plan.freq_start_hz <= freq_hz <= plan.freq_end_hz:
            return name
    return None


def get_band_plan(band: str) -> BandPlan | None:
    """Get band plan by name."""
    return BAND_PLANS.get(band)


def is_frequency_in_band(freq_hz: float, band: str) -> bool:
    """Check if frequency is within a band."""
    plan = BAND_PLANS.get(band)
    if not plan:
        return False
    return plan.freq_start_hz <= freq_hz <= plan.freq_end_hz


def get_modes_for_band(band: str) -> list[str]:
    """Get allowed modes for a band."""
    plan = BAND_PLANS.get(band)
    return plan.modes if plan else []
