"""TX compliance: restricted bands (FCC §15.205), allowlist, and audit logging."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from radioshaq.radio.bands import BAND_PLANS, BandPlan, get_band_for_frequency

# FCC 47 CFR §15.205 restricted bands (MHz and GHz). Intentional radiation prohibited.
# Source: https://www.ecfr.gov/current/title-47/chapter-I/subchapter-A/part-15/subpart-C/section-15.205
# Stored as (low_hz, high_hz).
_RESTRICTED_BANDS_FCC_HZ: list[tuple[float, float]] = [
    # MHz ranges (convert to Hz)
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
    (108e6, 121.94e6),
    (123e6, 138e6),
    (149.9e6, 150.05e6),
    (156.52475e6, 156.52525e6),
    (156.7e6, 156.9e6),
    (162.0125e6, 167.17e6),
    (167.72e6, 173.2e6),
    (240e6, 285e6),
    (322e6, 335.4e6),
    (399.9e6, 410e6),
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
    # GHz ranges (convert to Hz)
    (4.5e9, 5.15e9),
    (5.35e9, 5.46e9),
    (7.25e9, 7.75e9),
    (8.025e9, 8.5e9),
    (9.0e9, 9.2e9),
    (9.3e9, 9.5e9),
    (10.6e9, 12.7e9),
    (13.25e9, 13.4e9),
    (14.47e9, 14.5e9),
    (15.35e9, 16.2e9),
    (17.7e9, 21.4e9),
    (22.01e9, 23.12e9),
    (23.6e9, 24.0e9),
    (31.2e9, 31.8e9),
    (36.43e9, 36.5e9),
    (38.6e9, 100e9),  # Above 38.6 GHz
]


def is_restricted(
    freq_hz: float,
    region: str = "FCC",
) -> bool:
    """
    Return True if the frequency falls in a restricted band (e.g. FCC §15.205).
    Intentional radiation is prohibited in these bands regardless of power.
    """
    if region != "FCC":
        # Future: CEPT or other region tables
        return False
    for low, high in _RESTRICTED_BANDS_FCC_HZ:
        if low <= freq_hz <= high:
            return True
    return False


def is_tx_allowed(
    freq_hz: float,
    band_plan_source: dict[str, BandPlan] | None = None,
    allow_tx_only_amateur_bands: bool = True,
    restricted_region: str = "FCC",
) -> bool:
    """
    Return True only if TX is allowed on this frequency:
    - Not in a restricted band (FCC §15.205 or equivalent).
    - If allow_tx_only_amateur_bands is True, frequency must be within a band
      in band_plan_source (default BAND_PLANS).
    """
    if is_restricted(freq_hz, region=restricted_region):
        return False
    if not allow_tx_only_amateur_bands:
        return True
    plans = band_plan_source if band_plan_source is not None else BAND_PLANS
    for plan in plans.values():
        if plan.freq_start_hz <= freq_hz <= plan.freq_end_hz:
            return True
    return False


def log_tx(
    frequency_hz: float,
    duration_sec: float,
    mode: str,
    rig_or_sdr: str,
    operator_id: str | None = None,
    timestamp: datetime | None = None,
    audit_log_path: str | Path | None = None,
    **extra: Any,
) -> None:
    """
    Log a transmit event for audit. Writes one JSON line to audit_log_path if set,
    and always logs via loguru at INFO.
    """
    ts = timestamp or datetime.now(timezone.utc)
    payload = {
        "timestamp": ts.isoformat(),
        "frequency_hz": frequency_hz,
        "duration_sec": duration_sec,
        "mode": mode,
        "rig_or_sdr": rig_or_sdr,
        "operator_id": operator_id,
        **extra,
    }
    logger.info(
        "TX audit: freq={} Hz duration={}s mode={} rig={}",
        frequency_hz,
        duration_sec,
        mode,
        rig_or_sdr,
    )
    if audit_log_path:
        path = Path(audit_log_path)
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning("Could not write TX audit log to %s: %s", path, e)
