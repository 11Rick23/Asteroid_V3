from __future__ import annotations

import pytest

from app.database.migrations_check import validate_database_revision


def test_validate_database_revision_accepts_current_head() -> None:
    validate_database_revision(("abc123",), ("abc123",))


def test_validate_database_revision_rejects_missing_alembic_version() -> None:
    with pytest.raises(RuntimeError, match="Alembic revision が記録されていません") as error_info:
        validate_database_revision((), ("abc123",))
    message = str(error_info.value)
    assert "stamp head" not in message
    assert "uv run alembic stamp 273b6467e5ff" in message
    assert "uv run alembic upgrade head" in message


def test_validate_database_revision_rejects_old_revision() -> None:
    with pytest.raises(RuntimeError, match="Alembic revision が最新ではありません"):
        validate_database_revision(("old123",), ("abc123",))
