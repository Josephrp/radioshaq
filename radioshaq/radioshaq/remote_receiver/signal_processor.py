"""Signal detection, decoding, and filtering (stub)."""

from __future__ import annotations

from radioshaq.remote_receiver.radio_interface import SignalSample


def is_interesting(sample: SignalSample, threshold_db: float = -90.0) -> bool:
    """True if signal strength above threshold (simple gate)."""
    return sample.strength_db >= threshold_db


def decode_digital(sample: SignalSample) -> str:
    """Placeholder: decode digital mode from raw_data; return empty if none."""
    if sample.decoded_data:
        return sample.decoded_data
    return ""
