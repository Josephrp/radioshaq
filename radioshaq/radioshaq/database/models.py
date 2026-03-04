"""SQLAlchemy models for SHAKODS database.

Defines the core database schema with PostGIS support for
location-based operations and ham radio coordination.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    
    pass


class OperatorLocation(Base):
    """GIS-enabled table for storing operator locations.
    
    Tracks the geographic location of ham radio operators for
    coordination, propagation analysis, and mapping.
    """
    
    __tablename__ = "operator_locations"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    callsign: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    
    # Geographic location (PostGIS Point with WGS 84 SRID)
    # SRID 4326 = WGS 84 (latitude/longitude)
    location: Mapped[Any] = mapped_column(
        Geometry("POINT", srid=4326),
        nullable=False,
    )
    
    # Additional location data
    altitude_meters: Mapped[float | None] = mapped_column(Float)
    accuracy_meters: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(
        String(50),
        default="manual",
        doc="Source of location data: gps, manual, aprs, grid_square",
    )
    
    # Timestamps
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # Session/operator reference
    session_id: Mapped[str | None] = mapped_column(String(100), index=True)
    
    # Relationships
    transcripts: Mapped[list["Transcript"]] = relationship(
        "Transcript",
        back_populates="operator",
        lazy="selectin",
    )
    
    # Geo-index for efficient spatial queries
    __table_args__ = (
        Index(
            "ix_operator_locations_location",
            "location",
            postgresql_using="GIST",  # GIST index for spatial queries
        ),
    )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "callsign": self.callsign,
            "location": self.location,
            "altitude_meters": self.altitude_meters,
            "accuracy_meters": self.accuracy_meters,
            "source": self.source,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "session_id": self.session_id,
        }


class RegisteredCallsign(Base):
    """Registry of allowed callsigns (whitelist). Merged with config allowed_callsigns."""

    __tablename__ = "registered_callsigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    callsign: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="api")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    preferred_bands: Mapped[list | None] = mapped_column(JSON, nullable=True)  # e.g. ["40m", "2m"]
    last_band: Mapped[str | None] = mapped_column(String(20), nullable=True)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "callsign": self.callsign,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "preferred_bands": self.preferred_bands,
            "last_band": self.last_band,
        }


class Transcript(Base):
    """Storage for radio communication transcripts.
    
    Records all radio communications with GIS context for
    logging, analysis, and retrieval.
    """
    
    __tablename__ = "transcripts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Session identification
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    
    # Timestamps
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )
    
    # Radio information
    source_callsign: Mapped[str] = mapped_column(String(20), index=True)
    destination_callsign: Mapped[str | None] = mapped_column(String(20))
    frequency_hz: Mapped[float] = mapped_column(Float, index=True)
    mode: Mapped[str] = mapped_column(String(20))  # FM, SSB, CW, PSK31, FT8, etc.
    
    # Transcript content
    transcript_text: Mapped[str] = mapped_column(Text)
    raw_audio_path: Mapped[str | None] = mapped_column(String(500))  # Path to S3/local storage
    
    # Quality metrics
    signal_quality: Mapped[float | None] = mapped_column(
        Float,
        doc="Signal quality 0.0-1.0",
    )
    signal_strength_db: Mapped[float | None] = mapped_column(
        Float,
        doc="Signal strength in dB",
    )
    
    # Source reference (who/where this was received)
    operator_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("operator_locations.id"),
    )
    
    # Foreign relationships
    operator: Mapped[OperatorLocation | None] = relationship(
        "OperatorLocation",
        back_populates="transcripts",
    )
    
    # Additional metadata (JSON for flexibility)
    extra_data: Mapped[dict | None] = mapped_column(
        JSON,
        doc="Additional metadata: radio_model, antenna, weather, etc.",
    )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "source_callsign": self.source_callsign,
            "destination_callsign": self.destination_callsign,
            "frequency_hz": self.frequency_hz,
            "mode": self.mode,
            "transcript_text": self.transcript_text,
            "raw_audio_path": self.raw_audio_path,
            "signal_quality": self.signal_quality,
            "operator_location_id": self.operator_location_id,
            "extra_data": self.extra_data,
        }


class CoordinationEvent(Base):
    """Coordination events between operators.
    
    Tracks scheduled contacts, relay requests, and other
    coordination activities.
    """
    
    __tablename__ = "coordination_events"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Event type
    event_type: Mapped[str] = mapped_column(
        String(50),
        doc="Type: schedule, relay, emergency, net_check_in, etc.",
    )
    
    # Participants
    initiator_callsign: Mapped[str] = mapped_column(String(20), index=True)
    target_callsign: Mapped[str | None] = mapped_column(String(20), index=True)
    
    # Scheduled details
    scheduled_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    frequency_hz: Mapped[float | None] = mapped_column(Float)
    mode: Mapped[str | None] = mapped_column(String(20))
    
    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        doc="Status: pending, completed, cancelled, missed",
    )
    
    # Location (for propagation planning)
    location: Mapped[Any | None] = mapped_column(
        Geometry("POINT", srid=4326),
        doc="Meeting point or relay location",
    )
    
    # Additional data
    priority: Mapped[int] = mapped_column(
        Integer,
        default=5,
        doc="Priority 1-10, lower = higher priority",
    )
    notes: Mapped[str | None] = mapped_column(Text)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    
    # Orchestrator reference
    task_id: Mapped[str | None] = mapped_column(String(100), index=True)
    
    # Metadata
    extra_data: Mapped[dict | None] = mapped_column(
        JSON,
        doc="Additional event data",
    )
    
    # Geo-index for location queries
    __table_args__ = (
        Index(
            "ix_coordination_events_location",
            "location",
            postgresql_using="GIST",
        ),
    )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "event_type": self.event_type,
            "initiator_callsign": self.initiator_callsign,
            "target_callsign": self.target_callsign,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "frequency_hz": self.frequency_hz,
            "mode": self.mode,
            "status": self.status,
            "priority": self.priority,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SessionState(Base):
    """Persistent session state for REACT orchestrator.
    
    Stores the state of long-running orchestrator tasks
    for recovery and inspection.
    """
    
    __tablename__ = "session_states"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    task_id: Mapped[str] = mapped_column(String(100), index=True)
    
    # State data
    phase: Mapped[str] = mapped_column(String(50))
    state_data: Mapped[dict] = mapped_column(JSON)
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        doc="Status: active, completed, failed, cancelled",
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# =============================================================================
# Indexes for common queries
# =============================================================================

# Create additional indexes for performance
Index("ix_transcripts_timestamp_frequency", Transcript.timestamp, Transcript.frequency_hz)
Index("ix_coordination_events_status_time", CoordinationEvent.status, CoordinationEvent.scheduled_time)
Index("ix_operator_locations_callsign_time", OperatorLocation.callsign, OperatorLocation.timestamp)
