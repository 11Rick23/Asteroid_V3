"""add leveling hotness events

Revision ID: 8f2a6c4b9d31
Revises: 273b6467e5ff
Create Date: 2026-06-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "8f2a6c4b9d31"
down_revision: str | Sequence[str] | None = "273b6467e5ff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "leveling_hotness_events",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("amount", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("earned_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_leveling_hotness_events_earned_at_user_id",
        "leveling_hotness_events",
        ["earned_at", "user_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_leveling_hotness_events_earned_at_user_id", table_name="leveling_hotness_events")
    op.drop_table("leveling_hotness_events")
