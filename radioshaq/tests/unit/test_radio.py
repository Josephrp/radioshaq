"""Unit tests for radio band plans and propagation (no hardware)."""

import pytest

from radioshaq.radio.bands import BAND_PLANS, get_band_for_frequency
from radioshaq.database.gis import propagation_prediction


@pytest.mark.unit
def test_band_plans_has_entries():
    """BAND_PLANS contains expected bands."""
    assert len(BAND_PLANS) > 0
    assert "40m" in BAND_PLANS
    for name, plan in BAND_PLANS.items():
        assert plan.name == name
        assert plan.freq_start_hz < plan.freq_end_hz
        assert len(plan.modes) >= 1


@pytest.mark.unit
def test_get_band_for_frequency():
    """get_band_for_frequency returns band name or None."""
    assert get_band_for_frequency(7.2e6) == "40m"
    assert get_band_for_frequency(145.0e6) == "2m"
    assert get_band_for_frequency(1.0) is None


@pytest.mark.unit
def test_propagation_prediction_structure():
    """propagation_prediction returns dict with distance_km, suggested_bands, notes."""
    out = propagation_prediction(0.0, 0.0, 1.0, 1.0)
    assert isinstance(out, dict)
    assert "distance_km" in out
    assert "suggested_bands" in out
    assert "notes" in out
    assert isinstance(out["suggested_bands"], list)
