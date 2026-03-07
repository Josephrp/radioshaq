"""Compliance backends: FCC, CEPT, ITU R1/R3, R2 Americas, R1 Africa, etc."""

from .au import AUBackend
from .ca import CABackend
from .cept import (
    BEBackend,
    CEPTBackend,
    CHBackend,
    ESBackend,
    FRBackend,
    LUBackend,
    MCBackend,
    UKBackend,
)
from .fcc import FCCBackend
from .in_ import INBackend
from .itu_r1 import ITUR1Backend
from .itu_r3 import ITUR3Backend
from .jp import JPBackend
from .mx import MXBackend
from .nz import NZBackend
from .r1_africa import R1AfricaBackend
from .r2_americas import R2AmericasBackend
from .za import ZABackend

__all__ = [
    "AUBackend",
    "BEBackend",
    "CABackend",
    "CEPTBackend",
    "CHBackend",
    "ESBackend",
    "FCCBackend",
    "FRBackend",
    "INBackend",
    "ITUR1Backend",
    "ITUR3Backend",
    "JPBackend",
    "LUBackend",
    "MCBackend",
    "MXBackend",
    "NZBackend",
    "R1AfricaBackend",
    "R2AmericasBackend",
    "UKBackend",
    "ZABackend",
]
