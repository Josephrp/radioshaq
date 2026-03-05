"""memory_tables

RadioShaq memory tables: core blocks, history, system instructions, messages, daily summaries.
Hindsight manages its own schema; this migration is for RadioShaq only.

Revision ID: a1b2c3d4e5f6
Revises: 8bc21f712e9b
Create Date: 2026-03-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "8bc21f712e9b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # memory_core_blocks: per-callsign editable blocks (user, identity, ideaspace)
    op.create_table(
        "memory_core_blocks",
        sa.Column("callsign", sa.String(length=20), nullable=False),
        sa.Column("block_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("callsign", "block_type"),
    )
    op.create_index(
        "ix_memory_core_blocks_callsign",
        "memory_core_blocks",
        ["callsign"],
        unique=False,
    )

    # memory_core_history: version history for core blocks
    op.create_table(
        "memory_core_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("callsign", sa.String(length=20), nullable=False),
        sa.Column("block_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_memory_core_history_callsign_block_type",
        "memory_core_history",
        ["callsign", "block_type"],
        unique=False,
    )

    # memory_system_instructions: global read-only (single row id=1)
    op.create_table(
        "memory_system_instructions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        "INSERT INTO memory_system_instructions (id, content, updated_at) "
        "VALUES (1, '', NOW()) ON CONFLICT (id) DO NOTHING"
    )

    # memory_messages: conversation history per callsign
    op.create_table(
        "memory_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("callsign", sa.String(length=20), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_memory_messages_callsign",
        "memory_messages",
        ["callsign"],
        unique=False,
    )
    op.create_index(
        "ix_memory_messages_callsign_created_at",
        "memory_messages",
        ["callsign", "created_at"],
        unique=False,
    )

    # memory_daily_summaries: one row per callsign per day
    op.create_table(
        "memory_daily_summaries",
        sa.Column("callsign", sa.String(length=20), nullable=False),
        sa.Column("summary_date", sa.Date(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("callsign", "summary_date"),
    )
    op.create_index(
        "ix_memory_daily_summaries_callsign",
        "memory_daily_summaries",
        ["callsign"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_memory_daily_summaries_callsign", "memory_daily_summaries")
    op.drop_table("memory_daily_summaries")

    op.drop_index("ix_memory_messages_callsign_created_at", "memory_messages")
    op.drop_index("ix_memory_messages_callsign", "memory_messages")
    op.drop_table("memory_messages")

    op.drop_table("memory_system_instructions")

    op.drop_index("ix_memory_core_history_callsign_block_type", "memory_core_history")
    op.drop_table("memory_core_history")

    op.drop_index("ix_memory_core_blocks_callsign", "memory_core_blocks")
    op.drop_table("memory_core_blocks")
