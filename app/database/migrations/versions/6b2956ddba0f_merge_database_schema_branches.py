"""merge database schema branches

Revision ID: 6b2956ddba0f
Revises: 2d91613550c1, 9f0a2c7d4b6e
Create Date: 2026-06-26 01:53:56.383334

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "6b2956ddba0f"
down_revision: str | Sequence[str] | None = ("2d91613550c1", "9f0a2c7d4b6e")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
