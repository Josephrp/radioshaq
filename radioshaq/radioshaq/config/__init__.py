"""Configuration system for RadioShaq.

Provides Pydantic-based configuration with support for:
- YAML/JSON config files
- Environment variables
- Validation and defaults
"""

from radioshaq.config.schema import (
    Config,
    DatabaseConfig,
    FieldConfig,
    HQConfig,
    JWTConfig,
    LLMConfig,
    MemoryConfig,
    PM2Config,
    RadioConfig,
)
from radioshaq.config.resolve import get_llm_config_for_role, get_memory_config_for_role

__all__ = [
    "Config",
    "DatabaseConfig",
    "FieldConfig",
    "HQConfig",
    "JWTConfig",
    "LLMConfig",
    "MemoryConfig",
    "PM2Config",
    "RadioConfig",
    "get_llm_config_for_role",
    "get_memory_config_for_role",
]
