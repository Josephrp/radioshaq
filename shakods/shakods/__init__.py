"""SHAKODS: Strategic Autonomous Ham Radio and Knowledge Operations Dispatch System.

A specialized derivative of nanobot implementing REACT (Reasoning, Evaluation,
Acting, Communicating, Tracking) agent orchestration pattern for ham radio
operations, emergency communications, and field-to-HQ coordination.
"""

from __future__ import annotations

__version__ = "0.1.0"
__logo__ = "📡"
__description__ = "Strategic Autonomous Ham Radio and Knowledge Operations Dispatch System"

# Import key components for convenient access
from shakods.config.schema import Config, FieldConfig, HQConfig, DatabaseConfig

__all__ = [
    "__version__",
    "__logo__",
    "__description__",
    "Config",
    "FieldConfig", 
    "HQConfig",
    "DatabaseConfig",
]
