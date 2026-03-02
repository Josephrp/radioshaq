"""Initial schema with PostGIS support

Revision ID: 0001
Revises: 
Create Date: 2025-02-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial SHAKODS database schema with PostGIS support."""
    
    # Create PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    
    # ==========================================
    # operator_locations table
    # ==========================================
    op.create_table(
        "operator_locations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("callsign", sa.String(length=20), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.Geometry(
                geometry_type="POINT",
                srid=4326,
                spatial_index=False,
            ),
            nullable=False,
        ),
        sa.Column("altitude_meters", sa.Float(), nullable=True),
        sa.Column("accuracy_meters", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("session_id", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Create indexes for operator_locations
    op.create_index("ix_operator_locations_callsign", "operator_locations", ["callsign"])
    op.create_index("ix_operator_locations_timestamp", "operator_locations", ["timestamp"])
    op.create_index("ix_operator_locations_session_id", "operator_locations", ["session_id"])
    # GIST index for spatial queries (PostGIS-specific)
    op.execute(
        "CREATE INDEX ix_operator_locations_location ON operator_locations USING GIST (location)"
    )
    op.create_index(
        "ix_operator_locations_callsign_time",
        "operator_locations",
        ["callsign", "timestamp"],
    )
    
    # ==========================================
    # transcripts table
    # ==========================================
    op.create_table(
        "transcripts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("source_callsign", sa.String(length=20), nullable=False),
        sa.Column("destination_callsign", sa.String(length=20), nullable=True),
        sa.Column("frequency_hz", sa.Float(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("transcript_text", sa.Text(), nullable=False),
        sa.Column("raw_audio_path", sa.String(length=500), nullable=True),
        sa.Column("signal_quality", sa.Float(), nullable=True),
        sa.Column("signal_strength_db", sa.Float(), nullable=True),
        sa.Column(
            "operator_location_id",
            sa.Integer(),
            sa.ForeignKey("operator_locations.id"),
            nullable=True,
        ),
        sa.Column("extra_data", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Create indexes for transcripts
    op.create_index("ix_transcripts_session_id", "transcripts", ["session_id"])
    op.create_index("ix_transcripts_timestamp", "transcripts", ["timestamp"])
    op.create_index("ix_transcripts_source_callsign", "transcripts", ["source_callsign"])
    op.create_index("ix_transcripts_frequency_hz", "transcripts", ["frequency_hz"])
    op.create_index(
        "ix_transcripts_timestamp_frequency",
        "transcripts",
        ["timestamp", "frequency_hz"],
    )
    
    # ==========================================
    # coordination_events table
    # ==========================================
    op.create_table(
        "coordination_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("initiator_callsign", sa.String(length=20), nullable=False),
        sa.Column("target_callsign", sa.String(length=20), nullable=True),
        sa.Column("scheduled_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("frequency_hz", sa.Float(), nullable=True),
        sa.Column("mode", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column(
            "location",
            geoalchemy2.Geometry(
                geometry_type="POINT",
                srid=4326,
                spatial_index=False,
            ),
            nullable=True,
        ),
        sa.Column("priority", sa.Integer(), server_default=sa.text("5"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("task_id", sa.String(length=100), nullable=True),
        sa.Column("extra_data", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Create indexes for coordination_events
    op.create_index("ix_coordination_events_initiator", "coordination_events", ["initiator_callsign"])
    op.create_index("ix_coordination_events_target", "coordination_events", ["target_callsign"])
    op.create_index("ix_coordination_events_scheduled_time", "coordination_events", ["scheduled_time"])
    op.create_index("ix_coordination_events_status", "coordination_events", ["status"])
    op.create_index("ix_coordination_events_task_id", "coordination_events", ["task_id"])
    # GIST index for location
    op.execute(
        "CREATE INDEX ix_coordination_events_location ON coordination_events USING GIST (location)"
    )
    op.create_index(
        "ix_coordination_events_status_time",
        "coordination_events",
        ["status", "scheduled_time"],
    )
    
    # ==========================================
    # session_states table
    # ==========================================
    op.create_table(
        "session_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False, unique=True),
        sa.Column("task_id", sa.String(length=100), nullable=False),
        sa.Column("phase", sa.String(length=50), nullable=False),
        sa.Column("state_data", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    
    # Create indexes for session_states
    op.create_index("ix_session_states_session_id", "session_states", ["session_id"])
    op.create_index("ix_session_states_task_id", "session_states", ["task_id"])
    op.create_index("ix_session_states_status", "session_states", ["status"])
    
    # Initial schema migration complete with PostGIS support


def downgrade() -> None:
    """Drop all SHAKODS tables."""
    
    # Drop tables in reverse order of dependencies
    op.drop_table("session_states")
    op.drop_table("coordination_events")
    op.drop_table("transcripts")
    op.drop_table("operator_locations")
    
    # Note: We keep PostGIS extension as it may be used by other applications
    # Schema downgrade complete
