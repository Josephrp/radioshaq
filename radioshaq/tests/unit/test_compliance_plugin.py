"""Unit tests for compliance plugin: backends, registry, CEPT/R1."""

from __future__ import annotations

import pytest

from radioshaq.compliance_plugin import get_backend, get_band_plan_source_for_config
from radioshaq.radio.compliance import is_restricted, is_tx_allowed


def test_get_backend_fcc():
    """FCC backend is registered and returns restricted bands."""
    b = get_backend("FCC")
    assert b is not None
    assert b.region_key == "FCC"
    bands = b.get_restricted_bands_hz()
    assert len(bands) > 0
    assert (0.090e6, 0.110e6) in bands or any(low == 0.09e6 for low, _ in bands)
    assert b.get_band_plans() is None


def test_get_backend_cept():
    """CEPT backend is registered and provides R1 band plan."""
    b = get_backend("CEPT")
    assert b is not None
    assert b.region_key == "CEPT"
    bands = b.get_restricted_bands_hz()
    assert len(bands) > 0
    plans = b.get_band_plans()
    assert plans is not None
    assert "2m" in plans
    assert plans["2m"].freq_start_hz == 144.0e6
    assert plans["2m"].freq_end_hz == 146.0e6
    assert "70cm" in plans
    assert plans["70cm"].freq_start_hz == 430.0e6
    assert plans["70cm"].freq_end_hz == 440.0e6


def test_get_backend_itu_r1():
    """ITU_R1 backend is band-plan only (no restricted bands)."""
    b = get_backend("ITU_R1")
    assert b is not None
    assert b.region_key == "ITU_R1"
    assert b.get_restricted_bands_hz() == []
    plans = b.get_band_plans()
    assert plans is not None
    assert plans["2m"].freq_end_hz == 146.0e6


def test_is_restricted_cept_amateur_2m():
    """145 MHz is not restricted in CEPT and is in R1 2m."""
    assert is_restricted(145e6, region="CEPT") is False


def test_is_restricted_cept_known_restricted():
    """108–121.94 MHz is restricted in CEPT."""
    assert is_restricted(115e6, region="CEPT") is True


def test_is_tx_allowed_cept_r1_2m():
    """TX allowed at 145 MHz when CEPT backend provides R1 (145 in 2m 144–146)."""
    assert is_tx_allowed(
        145e6,
        band_plan_source=None,
        allow_tx_only_amateur_bands=True,
        restricted_region="CEPT",
    ) is True


def test_is_tx_allowed_cept_r1_2m_upper_out():
    """146.5 MHz is outside R1 2m (144–146), so not allowed when backend is CEPT."""
    assert is_tx_allowed(
        146.5e6,
        band_plan_source=None,
        allow_tx_only_amateur_bands=True,
        restricted_region="CEPT",
    ) is False


def test_get_backend_unknown():
    """Unknown region returns None."""
    assert get_backend("UNKNOWN") is None


def test_is_restricted_unknown_region_false():
    """Unknown region falls back to no restricted bands (legacy behaviour)."""
    assert is_restricted(115e6, region="UNKNOWN") is False


def test_get_backend_uk_es_mx_au():
    """UK, ES, MX, AU backends are registered and return expected data."""
    uk = get_backend("UK")
    assert uk is not None
    assert uk.region_key == "UK"
    assert uk.get_band_plans() is not None
    assert uk.get_band_plans()["2m"].freq_end_hz == 146.0e6
    es = get_backend("ES")
    assert es is not None
    assert es.region_key == "ES"
    mx = get_backend("MX")
    assert mx is not None
    assert mx.region_key == "MX"
    assert mx.get_band_plans() is None
    assert len(mx.get_restricted_bands_hz()) > 0
    au = get_backend("AU")
    assert au is not None
    assert au.region_key == "AU"
    assert au.get_band_plans() is not None
    assert au.get_band_plans()["2m"].freq_end_hz == 148.0e6  # R3
    assert au.get_band_plans()["70cm"].freq_end_hz == 440.0e6
    assert len(au.get_restricted_bands_hz()) > 0


def test_get_backend_be_ch_lu_mc_ca():
    """French/European CEPT and Canada backends are registered."""
    for key in ("BE", "CH", "LU", "MC"):
        b = get_backend(key)
        assert b is not None, key
        assert b.region_key == key
        assert b.get_band_plans() is not None
        assert b.get_band_plans()["2m"].freq_end_hz == 146.0e6
    ca = get_backend("CA")
    assert ca is not None
    assert ca.region_key == "CA"
    assert ca.get_band_plans() is None
    assert len(ca.get_restricted_bands_hz()) > 0


def test_get_backend_r2_americas():
    """R2 Americas country backends (AR, CL, CO, PE, etc.) are registered."""
    for key in ("AR", "CL", "CO", "PE", "VE", "EC", "UY", "DO"):
        b = get_backend(key)
        assert b is not None, key
        assert b.region_key == key
        assert b.get_band_plans() is None
        assert len(b.get_restricted_bands_hz()) > 0


def test_get_band_plan_source_for_config():
    """Effective band plan respects restricted_region and band_plan_region."""
    # FCC: no backend band plan → BAND_PLANS (R2)
    plans = get_band_plan_source_for_config("FCC", None)
    assert "2m" in plans
    assert plans["2m"].freq_end_hz == 148.0e6  # R2
    # CEPT: backend provides R1
    plans_cept = get_band_plan_source_for_config("CEPT", None)
    assert plans_cept["2m"].freq_end_hz == 146.0e6
    # Override band_plan_region to ITU_R1 when restricted is FCC
    plans_r1 = get_band_plan_source_for_config("FCC", "ITU_R1")
    assert plans_r1["2m"].freq_end_hz == 146.0e6
    # AU: R3 band plan (2m 144-148, 70cm 430-440)
    plans_au = get_band_plan_source_for_config("AU", None)
    assert plans_au["2m"].freq_end_hz == 148.0e6
    assert plans_au["70cm"].freq_end_hz == 440.0e6
    # ITU_R3 band-plan-only
    r3 = get_backend("ITU_R3")
    assert r3 is not None
    assert r3.get_band_plans()["2m"].freq_end_hz == 148.0e6
    assert r3.get_band_plans()["70cm"].freq_end_hz == 440.0e6


def test_au_restricted_bands_enforced():
    """AU backend enforces restricted bands (ACMA conservative set)."""
    au = get_backend("AU")
    assert au is not None
    assert len(au.get_restricted_bands_hz()) > 0
    assert is_restricted(115e6, region="AU") is True   # aeronautical
    assert is_restricted(145e6, region="AU") is False  # amateur 2m R3


def test_ng_restricted_bands_enforced():
    """NG (and other R1 Africa) enforce R1 conservative restricted list."""
    ng = get_backend("NG")
    assert ng is not None
    assert len(ng.get_restricted_bands_hz()) > 0
    assert is_restricted(115e6, region="NG") is True
    assert is_restricted(145e6, region="NG") is False


def test_za_restricted_bands_enforced():
    """ZA backend enforces restricted bands (ICASA NRFP conservative set)."""
    za = get_backend("ZA")
    assert za is not None
    assert len(za.get_restricted_bands_hz()) > 0
    assert is_restricted(115e6, region="ZA") is True   # aeronautical
    assert is_restricted(145e6, region="ZA") is False   # amateur 2m R1
    assert is_restricted(433.5e6, region="ZA") is False  # 70cm shared ISM/amateur, TX permitted


def test_get_backend_nz_jp_in():
    """NZ, JP, IN backends are registered with R3 band plan and enforced restricted bands."""
    for key in ("NZ", "JP", "IN"):
        b = get_backend(key)
        assert b is not None, key
        assert b.region_key == key
        assert b.get_band_plans() is not None
        assert b.get_band_plans()["2m"].freq_end_hz == 148.0e6
        assert len(b.get_restricted_bands_hz()) > 0
    assert is_restricted(115e6, region="NZ") is True
    assert is_restricted(145e6, region="JP") is False


def test_get_backend_r1_africa():
    """R1 Africa country backends (ZA, NG, KE, etc.) have R1 band plan and enforced restricted bands."""
    for key in ("ZA", "NG", "KE", "EG", "MA", "SN", "CI"):
        b = get_backend(key)
        assert b is not None, key
        assert b.region_key == key
        assert b.get_band_plans() is not None
        assert b.get_band_plans()["2m"].freq_end_hz == 146.0e6  # R1
        assert len(b.get_restricted_bands_hz()) > 0
