"""registered_callsigns preferred_bands and last_band

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-04 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "registered_callsigns",
        sa.Column("preferred_bands", sa.JSON(), nullable=True),
    )
    op.add_column(
        "registered_callsigns",
        sa.Column("last_band", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("registered_callsigns", "last_band")
    op.drop_column("registered_callsigns", "preferred_bands")
