"""Ham radio interfaces (CAT, digital modes, packet, compliance).

This package historically re-exported many convenience symbols. To keep imports
lightweight (and usable in minimal environments that don't have optional deps),
we lazily import these symbols on attribute access.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    # CAT / rig
    "HamlibCATControl",
    "RigState",
    "RigManager",
    # Band plans
    "BandPlan",
    "BAND_PLANS",
    "get_band_for_frequency",
    # Compliance
    "is_restricted",
    "is_tx_allowed",
    "is_tx_spectrum_allowed",
    "log_tx",
    # Digital / packet
    "FLDIGIInterface",
    "DigitalTransmission",
    "PacketRadioInterface",
    "AX25Frame",
    # Modes
    "ModeFamily",
    "ModeSpec",
    "RadioModeName",
    "normalize_mode",
    "spec_for",
    "hamlib_mode_for",
    "external_modem_for",
    # SDR TX
    "SDRTransmitter",
    "HackRFTransmitter",
]


_EXPORTS: dict[str, tuple[str, str]] = {
    # module, attribute
    "HamlibCATControl": ("radioshaq.radio.cat_control", "HamlibCATControl"),
    "RigState": ("radioshaq.radio.cat_control", "RigState"),
    "RigManager": ("radioshaq.radio.rig_manager", "RigManager"),
    "BandPlan": ("radioshaq.radio.bands", "BandPlan"),
    "BAND_PLANS": ("radioshaq.radio.bands", "BAND_PLANS"),
    "get_band_for_frequency": ("radioshaq.radio.bands", "get_band_for_frequency"),
    "is_restricted": ("radioshaq.radio.compliance", "is_restricted"),
    "is_tx_allowed": ("radioshaq.radio.compliance", "is_tx_allowed"),
    "is_tx_spectrum_allowed": ("radioshaq.radio.compliance", "is_tx_spectrum_allowed"),
    "log_tx": ("radioshaq.radio.compliance", "log_tx"),
    "FLDIGIInterface": ("radioshaq.radio.digital_modes", "FLDIGIInterface"),
    "DigitalTransmission": ("radioshaq.radio.digital_modes", "DigitalTransmission"),
    "PacketRadioInterface": ("radioshaq.radio.packet_radio", "PacketRadioInterface"),
    "AX25Frame": ("radioshaq.radio.packet_radio", "AX25Frame"),
    "ModeFamily": ("radioshaq.radio.modes", "ModeFamily"),
    "ModeSpec": ("radioshaq.radio.modes", "ModeSpec"),
    "RadioModeName": ("radioshaq.radio.modes", "RadioModeName"),
    "normalize_mode": ("radioshaq.radio.modes", "normalize_mode"),
    "spec_for": ("radioshaq.radio.modes", "spec_for"),
    "hamlib_mode_for": ("radioshaq.radio.modes", "hamlib_mode_for"),
    "external_modem_for": ("radioshaq.radio.modes", "external_modem_for"),
    "SDRTransmitter": ("radioshaq.radio.sdr_tx", "SDRTransmitter"),
    "HackRFTransmitter": ("radioshaq.radio.sdr_tx", "HackRFTransmitter"),
}


def __getattr__(name: str) -> Any:  # pragma: no cover
    if name not in _EXPORTS:
        raise AttributeError(name)
    mod_name, attr = _EXPORTS[name]
    mod = import_module(mod_name)
    return getattr(mod, attr)

