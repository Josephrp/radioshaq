"""add_registered_callsigns

Revision ID: 8bc21f712e9b
Revises: 0001
Create Date: 2026-03-03 15:30:36.733897

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "8bc21f712e9b"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "registered_callsigns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("callsign", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=20), server_default="api", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_registered_callsigns_callsign"),
        "registered_callsigns",
        ["callsign"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_registered_callsigns_callsign"),
        table_name="registered_callsigns",
    )
    op.drop_table("registered_callsigns")
