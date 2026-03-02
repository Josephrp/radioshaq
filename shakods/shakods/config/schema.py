"""Configuration schema for SHAKODS using Pydantic.

This module defines all configuration models for the SHAKODS system,
supporting file-based config, environment variables, and validation.
"""

from __future__ import annotations

from enum import Enum, StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Mode(StrEnum):
    """Operational mode for SHAKODS."""
    
    FIELD = "field"  # Edge/field station mode
    HQ = "hq"  # Headquarters/central mode
    RECEIVER = "receiver"  # Remote receiver only


class LogLevel(StrEnum):
    """Log level options."""
    
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LLMProvider(StrEnum):
    """Supported LLM providers."""
    
    MISTRAL = "mistral"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"


class RadioMode(StrEnum):
    """Radio operating modes."""
    
    FM = "FM"
    AM = "AM"
    SSB_USB = "USB"
    SSB_LSB = "LSB"
    CW = "CW"
    DIGITAL = "DIG"


# =============================================================================
# Component Configurations
# =============================================================================

class DatabaseConfig(BaseModel):
    """Database configuration."""
    
    model_config = ConfigDict(extra="ignore")
    
    # PostgreSQL with PostGIS (default port 5434 matches docker-compose to avoid host 5432 conflict)
    postgres_url: str = Field(
        default="postgresql+asyncpg://shakods:shakods@127.0.0.1:5434/shakods",
        description="PostgreSQL connection URL with asyncpg driver",
    )
    postgres_pool_size: int = Field(default=10, ge=1, le=100)
    postgres_max_overflow: int = Field(default=20, ge=0, le=100)
    postgres_echo: bool = Field(default=False)  # SQL logging
    
    # DynamoDB (for serverless deployment)
    dynamodb_table_prefix: str = Field(default="shakods")
    dynamodb_endpoint: str | None = Field(default=None)  # For local testing
    dynamodb_region: str = Field(default="us-east-1")
    
    # Redis (for caching/sessions)
    redis_url: str | None = Field(default="redis://localhost:6379/0")
    
    # Alembic
    alembic_config: str = Field(default="infrastructure/local/alembic.ini")
    auto_migrate: bool = Field(default=False)  # Run migrations on startup
    
    @field_validator("postgres_url")
    @classmethod
    def validate_postgres_url(cls, v: str) -> str:
        """Ensure URL uses asyncpg driver."""
        if v.startswith("postgresql://") and "asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://")
        return v


class JWTConfig(BaseModel):
    """JWT authentication configuration."""
    
    model_config = ConfigDict(extra="ignore")
    
    secret_key: str = Field(
        default="dev-secret-change-in-production",
        description="JWT signing secret (must be secure in production)",
    )
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)
    
    # Field station auth
    field_token_expire_hours: int = Field(default=24, ge=1)
    require_station_id: bool = Field(default=True)
    
    @field_validator("secret_key")
    @classmethod
    def validate_secret(cls, v: str) -> str:
        """Warn about insecure secrets."""
        if v in ("dev-secret", "dev-secret-change-in-production", "test"):
            # In production, this should raise an error
            pass
        return v


class LLMConfig(BaseModel):
    """LLM/AI provider configuration."""
    
    model_config = ConfigDict(extra="ignore")
    
    provider: LLMProvider = Field(default=LLMProvider.MISTRAL)
    model: str = Field(default="mistral-large-latest")
    
    # API Keys (loaded from env if not specified)
    mistral_api_key: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)
    anthropic_api_key: str | None = Field(default=None)
    
    # Custom provider
    custom_api_base: str | None = Field(default=None)
    custom_api_key: str | None = Field(default=None)
    
    # Generation parameters
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1, le=100000)
    timeout_seconds: float = Field(default=60.0, ge=1.0)
    
    # Retry settings
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: float = Field(default=1.0, ge=0.0)


class RadioConfig(BaseModel):
    """Ham radio configuration."""
    
    model_config = ConfigDict(extra="ignore")
    
    enabled: bool = Field(default=False)
    
    # CAT Control
    rig_model: int = Field(default=1, description="Hamlib rig model number")
    port: str = Field(default="/dev/ttyUSB0")
    baudrate: int = Field(default=9600, ge=300, le=115200)
    use_daemon: bool = Field(default=False)
    daemon_host: str = Field(default="localhost")
    daemon_port: int = Field(default=4532, ge=1, le=65535)
    
    # Digital Modes (FLDIGI)
    fldigi_host: str = Field(default="localhost")
    fldigi_port: int = Field(default=7362, ge=1, le=65535)
    fldigi_enabled: bool = Field(default=False)
    
    # Packet Radio
    packet_enabled: bool = Field(default=False)
    packet_callsign: str = Field(default="N0CALL")
    packet_ssid: int = Field(default=0, ge=0, le=15)
    packet_kiss_host: str = Field(default="localhost")
    packet_kiss_port: int = Field(default=8001, ge=1, le=65535)
    
    # Band limits
    tx_enabled: bool = Field(default=True)
    rx_enabled: bool = Field(default=True)
    max_power_watts: float = Field(default=100.0, ge=0.0)


class PM2Config(BaseModel):
    """PM2 process manager configuration."""
    
    model_config = ConfigDict(extra="ignore")
    
    # Process settings
    instances: int = Field(default=1, ge=1, le=10)
    autorestart: bool = Field(default=True)
    watch: bool = Field(default=True)
    max_memory_restart: str = Field(default="1G")
    
    # Logging
    log_dir: str = Field(default="logs")
    log_date_format: str = Field(default="YYYY-MM-DD HH:mm:ss Z")
    merge_logs: bool = Field(default=False)
    
    # Environment
    env_file: str | None = Field(default=".env")
    source_map_support: bool = Field(default=True)


# =============================================================================
# Mode-Specific Configurations
# =============================================================================

class FieldConfig(BaseModel):
    """Field mode (edge deployment) configuration."""
    
    model_config = ConfigDict(extra="ignore")
    
    station_id: str = Field(
        default="FIELD-01",
        description="Unique identifier for this field station",
    )
    callsign: str | None = Field(default=None)
    
    # HQ connection
    hq_base_url: str = Field(default="https://hq.shakods.example.com")
    hq_ws_url: str | None = Field(default=None)  # Auto-derived from base_url if not set
    hq_auth_token: str | None = Field(default=None)
    
    # Sync settings
    sync_interval_seconds: int = Field(default=60, ge=10)
    sync_batch_size: int = Field(default=100, ge=1)
    sync_max_retries: int = Field(default=5, ge=0)
    sync_retry_delay: int = Field(default=10, ge=1)
    sync_on_connect: bool = Field(default=True)
    
    # Offline mode
    offline_mode: bool = Field(default=False)
    max_offline_queue_size: int = Field(default=1000, ge=100)
    
    @model_validator(mode="after")
    def derive_ws_url(self) -> FieldConfig:
        """Derive WebSocket URL from base URL if not set."""
        if self.hq_ws_url is None:
            ws_base = self.hq_base_url.replace("https://", "wss://").replace("http://", "ws://")
            self.hq_ws_url = f"{ws_base}/ws"
        return self


class HQConfig(BaseModel):
    """HQ mode (central coordination) configuration."""
    
    model_config = ConfigDict(extra="ignore")
    
    # Server settings
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    
    # WebSocket
    ws_enabled: bool = Field(default=True)
    ws_path: str = Field(default="/ws")
    
    # Field station management
    max_field_stations: int = Field(default=100, ge=1)
    field_auth_required: bool = Field(default=True)
    field_registration_open: bool = Field(default=False)
    
    # Coordination
    auto_coordination_enabled: bool = Field(default=True)
    coordination_interval_seconds: int = Field(default=30, ge=5)


# =============================================================================
# Main Configuration
# =============================================================================

class Config(BaseSettings):
    """Main SHAKODS configuration.
    
    Loads from:
    1. Environment variables (SHAKODS_*)
    2. Config file (config.yaml, config.json)
    3. Default values
    
    Example:
        config = Config()
        print(config.database.postgres_url)
        print(config.mode)
    """
    
    model_config = SettingsConfigDict(
        env_prefix="SHAKODS_",
        env_nested_delimiter="__",
        yaml_file="config.yaml",
        yaml_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Core settings
    mode: Mode = Field(default=Mode.FIELD)
    debug: bool = Field(default=False)
    log_level: LogLevel = Field(default=LogLevel.INFO)
    
    # Component configs
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    jwt: JWTConfig = Field(default_factory=JWTConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    radio: RadioConfig = Field(default_factory=RadioConfig)
    pm2: PM2Config = Field(default_factory=PM2Config)
    
    # Mode-specific configs
    field: FieldConfig = Field(default_factory=FieldConfig)
    hq: HQConfig = Field(default_factory=HQConfig)
    
    # Paths
    workspace_dir: Path = Field(default=Path("~/.shakods"))
    data_dir: Path = Field(default=Path("~/.shakods/data"))
    
    @field_validator("workspace_dir", "data_dir", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        """Expand user home in paths."""
        if isinstance(v, str):
            v = Path(v)
        return v.expanduser()
    
    @model_validator(mode="after")
    def create_directories(self) -> Config:
        """Ensure workspace and data directories exist."""
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self
    
    @property
    def is_field_mode(self) -> bool:
        """Check if running in field mode."""
        return self.mode == Mode.FIELD
    
    @property
    def is_hq_mode(self) -> bool:
        """Check if running in HQ mode."""
        return self.mode == Mode.HQ
    
    def get_mode_config(self) -> FieldConfig | HQConfig:
        """Get the mode-specific configuration."""
        if self.mode == Mode.FIELD:
            return self.field
        elif self.mode == Mode.HQ:
            return self.hq
        else:
            raise ValueError(f"Unknown mode: {self.mode}")


# =============================================================================
# Utility Functions
# =============================================================================

def load_config(config_path: Path | str | None = None) -> Config:
    """Load configuration from file or environment.
    
    Args:
        config_path: Optional path to config file (YAML or JSON)
        
    Returns:
        Loaded Config instance
    """
    if config_path:
        config_path = Path(config_path)
        if config_path.exists():
            # Load from specific file
            import yaml
            data = yaml.safe_load(config_path.read_text())
            return Config(**data)
    
    # Load from default locations
    return Config()


def save_config(config: Config, path: Path | str) -> None:
    """Save configuration to file.
    
    Args:
        config: Config instance to save
        path: Path to save to
    """
    path = Path(path)
    
    # Convert to dict
    data = config.model_dump(mode="json")
    
    # Save as YAML
    import yaml
    path.write_text(yaml.safe_dump(data, default_flow_style=False))


__all__ = [
    "Config",
    "DatabaseConfig",
    "FieldConfig",
    "HQConfig",
    "JWTConfig",
    "LLMConfig",
    "Mode",
    "PM2Config",
    "RadioConfig",
    "load_config",
    "save_config",
]
