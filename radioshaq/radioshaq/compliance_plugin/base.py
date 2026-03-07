"""Compliance backend protocol: restricted bands and optional band plans per region."""

from __future__ import annotations

from typing import Protocol

from radioshaq.radio.bands import BandPlan


class ComplianceBackend(Protocol):
    """Provides restricted bands and optional band plans for a region/country."""

    @property
    def region_key(self) -> str:
        """Unique key for this backend (e.g. FCC, CEPT, FR)."""
        ...

    def get_restricted_bands_hz(self) -> list[tuple[float, float]]:
        """List of (low_hz, high_hz) where intentional radiation is prohibited. Empty = none enforced."""
        ...

    def get_band_plans(self) -> dict[str, BandPlan] | None:
        """Band plans for allowlist and /radio/bands. None = use default (e.g. R2 from bands.py)."""
        ...
