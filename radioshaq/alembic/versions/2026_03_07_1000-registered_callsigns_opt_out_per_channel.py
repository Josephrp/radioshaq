"""registered_callsigns per-channel opt-out (notify_opt_out_at_sms, notify_opt_out_at_whatsapp)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-07 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "registered_callsigns",
        sa.Column("notify_opt_out_at_sms", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "registered_callsigns",
        sa.Column("notify_opt_out_at_whatsapp", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("registered_callsigns", "notify_opt_out_at_whatsapp")
    op.drop_column("registered_callsigns", "notify_opt_out_at_sms")

