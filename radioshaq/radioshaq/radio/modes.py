"""Normalized radio mode model and mappings.

This module is the single source of truth for how a user-facing mode maps to:
- CAT/hamlib rig modes (FM/AM/USB/LSB/CW/DIG, etc.)
- SDR DSP pipelines (demod/mod choice + default bandwidth/deviation)
- External modem software (FLDIGI / WSJT-X) when applicable
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ModeFamily(StrEnum):
    ANALOG = "analog"
    DIGITAL_TEXT = "digital_text"
    DIGITAL_WEAK_SIGNAL = "digital_weak_signal"
    PACKET = "packet"


class RadioModeName(StrEnum):
    # Analog voice/audio families
    NFM = "NFM"  # narrow FM voice
    AM = "AM"
    USB = "USB"
    LSB = "LSB"
    CW = "CW"  # treated as audio-tone pipeline unless separately decoded

    # Digital (external decoders/encoders)
    FLDIGI = "FLDIGI"  # generic digital-text via FLDIGI
    PSK31 = "PSK31"
    RTTY = "RTTY"

    FT8 = "FT8"

    AX25 = "AX25"
    APRS = "APRS"


@dataclass(frozen=True)
class ModeSpec:
    """Mode definition with mappings and reasonable defaults."""

    name: RadioModeName
    family: ModeFamily
    # CAT/hamlib rig mode string (rigctld uses these names too)
    hamlib_mode: str
    # For modes that require an external modem, the modem name (e.g. FLDIGI modem string)
    external_modem: str | None = None
    # Default occupied bandwidth estimate (for compliance and DSP filter defaults)
    default_bandwidth_hz: float = 12_500.0
    # FM deviation (Hz) when applicable
    fm_deviation_hz: float | None = None


MODE_SPECS: dict[RadioModeName, ModeSpec] = {
    RadioModeName.NFM: ModeSpec(
        name=RadioModeName.NFM,
        family=ModeFamily.ANALOG,
        hamlib_mode="FM",
        default_bandwidth_hz=12_500.0,
        fm_deviation_hz=2_500.0,
    ),
    RadioModeName.AM: ModeSpec(
        name=RadioModeName.AM,
        family=ModeFamily.ANALOG,
        hamlib_mode="AM",
        default_bandwidth_hz=10_000.0,
    ),
    RadioModeName.USB: ModeSpec(
        name=RadioModeName.USB,
        family=ModeFamily.ANALOG,
        hamlib_mode="USB",
        default_bandwidth_hz=2_800.0,
    ),
    RadioModeName.LSB: ModeSpec(
        name=RadioModeName.LSB,
        family=ModeFamily.ANALOG,
        hamlib_mode="LSB",
        default_bandwidth_hz=2_800.0,
    ),
    RadioModeName.CW: ModeSpec(
        name=RadioModeName.CW,
        family=ModeFamily.ANALOG,
        hamlib_mode="CW",
        default_bandwidth_hz=500.0,
    ),
    RadioModeName.FLDIGI: ModeSpec(
        name=RadioModeName.FLDIGI,
        family=ModeFamily.DIGITAL_TEXT,
        hamlib_mode="DIG",
        external_modem="FLDIGI",
        default_bandwidth_hz=3_000.0,
    ),
    RadioModeName.PSK31: ModeSpec(
        name=RadioModeName.PSK31,
        family=ModeFamily.DIGITAL_TEXT,
        hamlib_mode="DIG",
        external_modem="PSK31",
        default_bandwidth_hz=100.0,
    ),
    RadioModeName.RTTY: ModeSpec(
        name=RadioModeName.RTTY,
        family=ModeFamily.DIGITAL_TEXT,
        hamlib_mode="DIG",
        external_modem="RTTY",
        default_bandwidth_hz=500.0,
    ),
    RadioModeName.FT8: ModeSpec(
        name=RadioModeName.FT8,
        family=ModeFamily.DIGITAL_WEAK_SIGNAL,
        hamlib_mode="DIG",
        external_modem="FT8",
        default_bandwidth_hz=3_000.0,
    ),
    RadioModeName.AX25: ModeSpec(
        name=RadioModeName.AX25,
        family=ModeFamily.PACKET,
        hamlib_mode="PKTUSB",
        external_modem="AX25",
        default_bandwidth_hz=3_000.0,
    ),
    RadioModeName.APRS: ModeSpec(
        name=RadioModeName.APRS,
        family=ModeFamily.PACKET,
        hamlib_mode="PKTUSB",
        external_modem="APRS",
        default_bandwidth_hz=3_000.0,
    ),
}


def normalize_mode(value: str | RadioModeName | None, *, default: RadioModeName = RadioModeName.NFM) -> RadioModeName:
    """Normalize a user/API mode string into a RadioModeName."""
    if value is None:
        return default
    if isinstance(value, RadioModeName):
        return value
    raw = str(value).strip().upper()
    if raw in ("FM", "NFM"):
        return RadioModeName.NFM
    if raw in ("USB", "SSB", "SSB_USB"):
        return RadioModeName.USB
    if raw in ("LSB", "SSB_LSB"):
        return RadioModeName.LSB
    if raw in ("AM",):
        return RadioModeName.AM
    if raw in ("CW",):
        return RadioModeName.CW
    if raw in ("DIG", "DIGITAL", "FLDIGI"):
        return RadioModeName.FLDIGI
    if raw in ("PSK31", "PSK"):
        return RadioModeName.PSK31
    if raw in ("RTTY",):
        return RadioModeName.RTTY
    if raw in ("FT8",):
        return RadioModeName.FT8
    if raw in ("AX25", "AX.25"):
        return RadioModeName.AX25
    if raw in ("APRS",):
        return RadioModeName.APRS
    return default


def spec_for(mode: str | RadioModeName | None) -> ModeSpec:
    m = normalize_mode(mode)
    return MODE_SPECS[m]


def hamlib_mode_for(mode: str | RadioModeName | None) -> str:
    """Return the hamlib/rigctld mode string for a given normalized mode."""
    return spec_for(mode).hamlib_mode


def external_modem_for(mode: str | RadioModeName | None) -> str | None:
    """Return external modem name (FLDIGI/FT8/etc.) if applicable."""
    return spec_for(mode).external_modem

