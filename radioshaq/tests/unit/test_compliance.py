"""Unit tests for TX compliance: restricted bands, is_tx_allowed, log_tx."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from radioshaq.radio import compliance
from radioshaq.radio.compliance import is_restricted, is_tx_allowed, log_tx
from radioshaq.radio.bands import BAND_PLANS


def test_is_restricted_fcc_known_bands():
    """FCC §15.205: known restricted frequencies return True."""
    assert is_restricted(0.1e6, region="FCC") is True   # 0.09-0.11 MHz
    assert is_restricted(108e6, region="FCC") is True   # 108-121.94 MHz
    assert is_restricted(2250e6, region="FCC") is True  # 2200-2300 MHz


def test_is_restricted_fcc_amateur_in_band():
    """Frequencies inside amateur bands and not in restricted list return False."""
    assert is_restricted(7.2e6, region="FCC") is False   # 40m
    assert is_restricted(14.2e6, region="FCC") is False  # 20m
    assert is_restricted(145e6, region="FCC") is False   # 2m


def test_is_restricted_itu_r1_warns_band_plan_only():
    """ITU_R1 is band-plan-only; is_restricted returns False and logs a one-time warning."""
    from unittest.mock import patch

    compliance._WARNED_RESTRICTED_REGIONS.discard("ITU_R1")
    with patch.object(compliance.logger, "warning") as mock_warn:
        result = is_restricted(144e6, region="ITU_R1")
    assert result is False
    mock_warn.assert_called_once()
    msg = mock_warn.call_args[0][0]
    assert "ITU_R1" in msg or "band-plan-only" in msg


def test_is_tx_allowed_in_band():
    """TX allowed when in BAND_PLANS and not restricted."""
    assert is_tx_allowed(7.2e6, allow_tx_only_amateur_bands=True) is True
    assert is_tx_allowed(144.5e6, allow_tx_only_amateur_bands=True) is True


def test_is_tx_allowed_restricted():
    """TX not allowed in restricted band even if in amateur plan (overlap)."""
    # 108-121.94 is restricted; no amateur band there
    assert is_tx_allowed(115e6, allow_tx_only_amateur_bands=True) is False


def test_is_tx_allowed_out_of_band():
    """TX not allowed when outside BAND_PLANS when allow_tx_only_amateur_bands=True."""
    assert is_tx_allowed(100e6, allow_tx_only_amateur_bands=True) is False
    assert is_tx_allowed(1e9, allow_tx_only_amateur_bands=True) is False


def test_is_tx_allowed_no_restriction_when_allow_false():
    """When allow_tx_only_amateur_bands=False, only restricted check applies."""
    assert is_tx_allowed(7.2e6, allow_tx_only_amateur_bands=False) is True
    assert is_tx_allowed(115e6, allow_tx_only_amateur_bands=False) is False


def test_log_tx_does_not_raise():
    """log_tx runs without raising (logger only, no file)."""
    log_tx(
        frequency_hz=7.2e6,
        duration_sec=1.0,
        mode="SSB",
        rig_or_sdr="cat",
    )


def test_log_tx_writes_file():
    """log_tx appends one JSON line when audit_log_path is set."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = f.name
    try:
        log_tx(
            frequency_hz=7.2e6,
            duration_sec=0.5,
            mode="FM",
            rig_or_sdr="hackrf",
            operator_id="test-op",
            audit_log_path=path,
        )
        lines = Path(path).read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["frequency_hz"] == 7.2e6
        assert data["duration_sec"] == 0.5
        assert data["mode"] == "FM"
        assert data["rig_or_sdr"] == "hackrf"
        assert data["operator_id"] == "test-op"
    finally:
        Path(path).unlink(missing_ok=True)
