"""normalize leveling hotness events schema

Revision ID: 9f0a2c7d4b6e
Revises: 8f2a6c4b9d31
Create Date: 2026-06-26 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "9f0a2c7d4b6e"
down_revision: str | Sequence[str] | None = "8f2a6c4b9d31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index("ix_leveling_hotness_events_earned_at_user_id", table_name="leveling_hotness_events")
    op.alter_column(
        "leveling_hotness_events",
        "earned_at",
        existing_type=mysql.DATETIME(),
        server_default=sa.text("CURRENT_TIMESTAMP"),
        existing_nullable=False,
    )
    op.create_index(
        "idx_leveling_hotness_events_earned_at_user_id",
        "leveling_hotness_events",
        ["earned_at", "user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_leveling_hotness_events_earned_at_user_id", table_name="leveling_hotness_events")
    op.alter_column(
        "leveling_hotness_events",
        "earned_at",
        existing_type=mysql.DATETIME(),
        server_default=sa.func.now(),
        existing_nullable=False,
    )
    op.create_index(
        "ix_leveling_hotness_events_earned_at_user_id",
        "leveling_hotness_events",
        ["earned_at", "user_id"],
        unique=False,
    )
