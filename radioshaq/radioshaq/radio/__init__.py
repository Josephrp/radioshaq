"""Ham radio interfaces (CAT, digital modes, packet, compliance)."""

from radioshaq.radio.bands import BAND_PLANS, BandPlan, get_band_for_frequency
from radioshaq.radio.cat_control import HamlibCATControl, RigMode, RigState
from radioshaq.radio.compliance import is_restricted, is_tx_allowed, log_tx
from radioshaq.radio.digital_modes import FLDIGIInterface, DigitalTransmission
from radioshaq.radio.sdr_tx import HackRFTransmitter, SDRTransmitter
from radioshaq.radio.packet_radio import AX25Frame, PacketRadioInterface
from radioshaq.radio.rig_manager import RigManager

__all__ = [
    "HamlibCATControl",
    "RigMode",
    "RigState",
    "FLDIGIInterface",
    "DigitalTransmission",
    "PacketRadioInterface",
    "AX25Frame",
    "RigManager",
    "BandPlan",
    "BAND_PLANS",
    "get_band_for_frequency",
    "is_restricted",
    "is_tx_allowed",
    "log_tx",
    "SDRTransmitter",
    "HackRFTransmitter",
]
