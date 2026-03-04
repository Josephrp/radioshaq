"""transcripts_band_index

Add expression index on transcripts.extra_data->>'band' for efficient band filtering.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-04 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_transcripts_extra_data_band "
        "ON transcripts ((extra_data->>'band'))"
    )


def downgrade() -> None:
    op.drop_index("ix_transcripts_extra_data_band", table_name="transcripts")
