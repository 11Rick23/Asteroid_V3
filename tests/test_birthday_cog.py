from __future__ import annotations

from datetime import UTC, date, datetime

from app.features.birthday.cog import current_tokyo_date


def test_current_tokyo_date_uses_jst_boundary() -> None:
    now = datetime(2026, 4, 4, 15, 0, tzinfo=UTC)

    assert current_tokyo_date(now) == date(2026, 4, 5)


def test_current_tokyo_date_keeps_same_day_in_jst() -> None:
    now = datetime(2026, 4, 5, 3, 0, tzinfo=UTC)

    assert current_tokyo_date(now) == date(2026, 4, 5)
