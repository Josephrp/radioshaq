"""Unit tests for messaging_compliance.emergency_messaging_allowed (Project B1/B5)."""

import pytest

from radioshaq.config.schema import EmergencyContactConfig
from radioshaq.messaging_compliance import emergency_messaging_allowed


@pytest.mark.unit
def test_emergency_messaging_disabled_returns_false():
    """When config.enabled is False, always False."""
    config = EmergencyContactConfig(enabled=False, regions_allowed=["FCC", "CA"])
    assert emergency_messaging_allowed("FCC", config) is False
    assert emergency_messaging_allowed("CA", config) is False


@pytest.mark.unit
def test_emergency_messaging_region_not_in_allowlist_returns_false():
    """When enabled but region not in regions_allowed, False."""
    config = EmergencyContactConfig(enabled=True, regions_allowed=["FCC", "CA"])
    assert emergency_messaging_allowed("CEPT", config) is False
    assert emergency_messaging_allowed("ZA", config) is False


@pytest.mark.unit
def test_emergency_messaging_region_in_allowlist_returns_true():
    """When enabled and region in regions_allowed, True."""
    config = EmergencyContactConfig(enabled=True, regions_allowed=["FCC", "CA"])
    assert emergency_messaging_allowed("FCC", config) is True
    assert emergency_messaging_allowed("CA", config) is True
    assert emergency_messaging_allowed("fcc", config) is True
    assert emergency_messaging_allowed("  CA  ", config) is True


@pytest.mark.unit
def test_emergency_messaging_none_config_returns_false():
    """When config is None, False."""
    assert emergency_messaging_allowed("FCC", None) is False
