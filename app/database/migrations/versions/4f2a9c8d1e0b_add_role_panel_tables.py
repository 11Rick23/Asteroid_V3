"""add role panel tables

Revision ID: 4f2a9c8d1e0b
Revises: 273b6467e5ff
Create Date: 2026-07-06 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "4f2a9c8d1e0b"
down_revision: str | Sequence[str] | None = "273b6467e5ff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "role_panel_categories",
        sa.Column("category_id", mysql.INTEGER(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("display_order", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("requires_boost", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("category_id"),
    )
    op.create_table(
        "role_panel_roles",
        sa.Column("category_id", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("role_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("display_order", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["role_panel_categories.category_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("category_id", "role_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("role_panel_roles")
    op.drop_table("role_panel_categories")
