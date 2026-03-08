"""registered_callsigns contact preferences (notify-on-relay Section 8.1)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "registered_callsigns",
        sa.Column("notify_sms_phone", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "registered_callsigns",
        sa.Column("notify_whatsapp_phone", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "registered_callsigns",
        sa.Column("notify_on_relay", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "registered_callsigns",
        sa.Column("notify_consent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "registered_callsigns",
        sa.Column("notify_consent_source", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "registered_callsigns",
        sa.Column("notify_opt_out_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("registered_callsigns", "notify_opt_out_at")
    op.drop_column("registered_callsigns", "notify_consent_source")
    op.drop_column("registered_callsigns", "notify_consent_at")
    op.drop_column("registered_callsigns", "notify_on_relay")
    op.drop_column("registered_callsigns", "notify_whatsapp_phone")
    op.drop_column("registered_callsigns", "notify_sms_phone")
