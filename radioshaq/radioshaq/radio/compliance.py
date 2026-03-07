"""TX compliance: restricted bands (FCC §15.205), allowlist, and audit logging."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

from radioshaq.radio.bands import BAND_PLANS, BandPlan, get_band_for_frequency


def is_restricted(
    freq_hz: float,
    region: str = "FCC",
) -> bool:
    """
    Return True if the frequency falls in a restricted band (e.g. FCC §15.205).
    Intentional radiation is prohibited in these bands regardless of power.
    """
    from radioshaq.compliance_plugin import get_backend

    backend = get_backend(region)
    if backend is None:
        return False
    for low, high in backend.get_restricted_bands_hz():
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
    if band_plan_source is None:
        from radioshaq.compliance_plugin import get_backend

        b = get_backend(restricted_region)
        if b is not None and b.get_band_plans() is not None:
            band_plan_source = b.get_band_plans()
        else:
            band_plan_source = BAND_PLANS
    plans = band_plan_source
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
