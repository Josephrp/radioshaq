"""Configuration schema for SHAKODS using Pydantic.

This module defines all configuration models for the SHAKODS system,
supporting file-based config, environment variables, and validation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
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


class ResponseMode(StrEnum):
    """Response modes for radio audio reception."""
    LISTEN_ONLY = "listen_only"          # Transcribe only, no TX
    CONFIRM_FIRST = "confirm_first"      # Queue for human approval
    AUTO_RESPOND = "auto_respond"        # Full auto (use with caution)
    CONFIRM_TIMEOUT = "confirm_timeout"  # Auto-respond after timeout if not rejected


class VADMode(StrEnum):
    """WebRTC VAD aggressiveness presets."""
    NORMAL = "normal"      # Aggressiveness 0
    LOW_BITRATE = "low"    # Aggressiveness 1
    AGGRESSIVE = "aggressive"  # Aggressiveness 2
    VERY_AGGRESSIVE = "very_aggressive"  # Aggressiveness 3


class TriggerMatchMode(StrEnum):
    """How trigger phrases are matched."""
    EXACT = "exact"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    FUZZY = "fuzzy"  # Requires fuzzywuzzy or similar


class PendingResponseStatus(StrEnum):
    """Status of a pending response awaiting confirmation."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    AUTO_SENT = "auto_sent"


class AudioActivationMode(StrEnum):
    """When audio activation phrase is required."""
    SESSION = "session"       # Once heard, active until monitoring stops
    PER_MESSAGE = "per_message"  # Require phrase in each segment that is processed


# =============================================================================
# Component Configurations
# =============================================================================

class DatabaseConfig(BaseModel):
    """Database configuration."""
    
    model_config = ConfigDict(extra="ignore")
    
    # PostgreSQL with PostGIS (default port 5434 matches docker-compose to avoid host 5432 conflict)
    postgres_url: str = Field(
        default="postgresql+asyncpg://radioshaq:radioshaq@127.0.0.1:5434/radioshaq",
        description="PostgreSQL connection URL with asyncpg driver",
    )
    postgres_pool_size: int = Field(default=10, ge=1, le=100)
    postgres_max_overflow: int = Field(default=20, ge=0, le=100)
    postgres_echo: bool = Field(default=False)  # SQL logging
    
    # DynamoDB (for serverless deployment)
    dynamodb_table_prefix: str = Field(default="radioshaq")
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

    # Voice TX: play audio to rig (CAT rig + sound card)
    # audio_output_device: name or index of sound device that feeds rig line-in (None = default device)
    audio_output_device: str | int | None = Field(default=None)
    # If true, agent will use TTS to generate audio from message when no audio_path is provided
    voice_use_tts: bool = Field(default=False)

    # Compliance (TX allowlist, restricted bands, audit log)
    tx_audit_log_path: str | None = Field(default=None, description="Path to JSONL file for TX audit log")
    tx_allowed_bands_only: bool = Field(default=True, description="Only allow TX in band_plan bands")
    restricted_bands_region: str = Field(default="FCC", description="Region for restricted bands (FCC, CEPT)")

    # Callsign whitelist: static list merged with DB registered_callsigns
    allowed_callsigns: list[str] | None = Field(
        default=None,
        description="Static allowed callsigns; merged with DB registry. None = use only DB (or allow all if registry empty).",
    )
    callsign_registry_required: bool = Field(
        default=False,
        description="If True, only registered or config-allowed callsigns accepted for store/relay.",
    )

    @field_validator("allowed_callsigns", mode="before")
    @classmethod
    def normalize_allowed_callsigns(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        out = [x.strip().upper() for x in v if isinstance(x, str) and x.strip()]
        return out if out else None

    # SDR TX (HackRF) – off by default
    sdr_tx_enabled: bool = Field(default=False)
    sdr_tx_backend: str = Field(default="hackrf")
    sdr_tx_device_index: int = Field(default=0)
    sdr_tx_serial: str | None = Field(default=None, description="HackRF serial (optional)")
    sdr_tx_max_gain: int = Field(default=47, ge=0, le=47)
    sdr_tx_allow_bands_only: bool = Field(default=True)

    # Audio RX/TX integration (voice_rx pipeline)
    audio_input_enabled: bool = Field(default=False)
    audio_output_enabled: bool = Field(default=False)
    audio_monitoring_enabled: bool = Field(default=False)

    # Response formatting for radio (exit prompt / call-out)
    station_callsign: str | None = Field(
        default=None,
        description="Station callsign for reply call-out (e.g. 'N0CALL'). Defaults to packet_callsign if not set.",
    )
    response_radio_format_enabled: bool = Field(
        default=False,
        description="Wrap final reply in radio format: [station] de [caller] [message] Over/K.",
    )
    response_radio_format_style: str = Field(
        default="over",
        description="Sign-off style: 'over' | 'prosign' (K) | 'none'.",
    )


class MemoryConfig(BaseModel):
    """Per-callsign memory: core blocks, messages, daily summaries, Hindsight."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = Field(default=True)
    hindsight_base_url: str = Field(default="http://localhost:8888")
    hindsight_enabled: bool = Field(default=True)
    recent_messages_limit: int = Field(default=40)
    daily_summary_days: int = Field(default=7)
    summary_timezone: str = Field(default="America/New_York")


class AudioConfig(BaseModel):
    """Audio capture and processing configuration (voice_rx pipeline)."""

    model_config = ConfigDict(extra="ignore")

    # Input/Output devices
    input_device: str | int | None = Field(
        default=None,
        description="Audio input device (rig line-out)",
    )
    input_sample_rate: int = Field(default=16000)
    output_device: str | int | None = Field(
        default=None,
        description="Audio output device (rig line-in)",
    )

    # Preprocessing
    preprocessing_enabled: bool = Field(default=True)
    agc_enabled: bool = Field(default=True)
    agc_target_rms: float = Field(default=0.1, ge=0.01, le=1.0)
    highpass_filter_enabled: bool = Field(default=True)
    highpass_cutoff_hz: float = Field(default=80.0, ge=20.0, le=500.0)

    # Denoising
    denoising_enabled: bool = Field(default=True)
    denoising_backend: str = Field(default="rnnoise")  # "rnnoise", "spectral", "none"
    noise_calibration_seconds: float = Field(default=3.0, ge=1.0, le=10.0)
    min_snr_db: float = Field(default=3.0, ge=-10.0, le=40.0)

    # VAD
    vad_enabled: bool = Field(default=True)
    vad_threshold: float = Field(default=0.02)
    vad_mode: VADMode = Field(default=VADMode.AGGRESSIVE)
    pre_speech_buffer_ms: int = Field(default=300, ge=0, le=1000)
    post_speech_buffer_ms: int = Field(default=400, ge=0, le=1000)
    min_speech_duration_ms: int = Field(default=500, ge=100, le=2000)
    max_speech_duration_ms: int = Field(default=30000, ge=5000, le=60000)
    silence_duration_ms: int = Field(default=800, ge=200, le=2000)

    # ASR
    asr_model: str = Field(default="voxtral")
    asr_language: str = Field(default="en")
    asr_min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)

    # Response behavior
    auto_respond: bool = Field(default=False)  # Legacy; prefer response_mode
    response_mode: ResponseMode = Field(default=ResponseMode.LISTEN_ONLY)
    response_timeout_seconds: float = Field(default=30.0, ge=5.0, le=120.0)
    response_delay_ms: int = Field(default=500, ge=0, le=5000)
    response_cooldown_seconds: float = Field(default=5.0, ge=1.0, le=60.0)

    # Trigger filtering
    trigger_enabled: bool = Field(default=True)
    trigger_phrases: list[str] = Field(default_factory=lambda: ["radioshaq", "field station"])
    trigger_match_mode: TriggerMatchMode = Field(default=TriggerMatchMode.CONTAINS)
    trigger_callsign: str | None = Field(default=None)
    trigger_min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    # Optional audio activation: require phrase before processing
    audio_activation_enabled: bool = Field(default=False)
    audio_activation_phrase: str = Field(
        default="radioshaq",
        description="Phrase that must be heard before processing (when audio_activation_enabled).",
    )
    audio_activation_mode: AudioActivationMode = Field(
        default=AudioActivationMode.SESSION,
        description="Session: once activated, stay active. Per_message: require phrase in each processed segment.",
    )

    # PTT coordination
    ptt_coordination_enabled: bool = Field(default=True)
    ptt_cooldown_ms: int = Field(default=500, ge=100, le=2000)
    break_in_enabled: bool = Field(default=True)


class PendingResponse(BaseModel):
    """A pending response awaiting human confirmation (in-memory)."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(...)

    # Source
    incoming_transcript: str = Field(...)
    incoming_audio_path: str | None = None
    frequency_hz: float | None = None
    mode: str | None = None

    # Proposed response
    proposed_message: str = Field(...)
    proposed_audio_path: str | None = None

    # Status
    status: PendingResponseStatus = Field(default=PendingResponseStatus.PENDING)
    responded_at: datetime | None = None
    responded_by: str | None = None
    notes: str | None = None


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
    hq_base_url: str = Field(default="https://hq.radioshaq.example.com")
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
    """Main RadioShaq configuration.
    
    Loads from:
    1. Environment variables (RADIOSHAQ_*)
    2. Config file (config.yaml, config.json)
    3. Default values
    
    Example:
        config = Config()
        print(config.database.postgres_url)
        print(config.mode)
    """
    
    model_config = SettingsConfigDict(
        env_prefix="RADIOSHAQ_",
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
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    pm2: PM2Config = Field(default_factory=PM2Config)
    
    # Mode-specific configs
    field: FieldConfig = Field(default_factory=FieldConfig)
    hq: HQConfig = Field(default_factory=HQConfig)
    
    # Paths
    workspace_dir: Path = Field(default=Path("~/.radioshaq"))
    data_dir: Path = Field(default=Path("~/.radioshaq/data"))
    
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
    "AudioActivationMode",
    "AudioConfig",
    "Config",
    "MemoryConfig",
    "DatabaseConfig",
    "FieldConfig",
    "HQConfig",
    "JWTConfig",
    "LLMConfig",
    "Mode",
    "PendingResponse",
    "PendingResponseStatus",
    "PM2Config",
    "RadioConfig",
    "ResponseMode",
    "TriggerMatchMode",
    "VADMode",
    "load_config",
    "save_config",
]
