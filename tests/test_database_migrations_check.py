from __future__ import annotations

import pytest

from app.database.migrations_check import validate_database_revision


def test_validate_database_revision_accepts_current_head() -> None:
    validate_database_revision(("abc123",), ("abc123",))


def test_validate_database_revision_rejects_missing_alembic_version() -> None:
    with pytest.raises(RuntimeError, match="Alembic revision が記録されていません"):
        validate_database_revision((), ("abc123",))


def test_validate_database_revision_rejects_old_revision() -> None:
    with pytest.raises(RuntimeError, match="Alembic revision が最新ではありません"):
        validate_database_revision(("old123",), ("abc123",))
