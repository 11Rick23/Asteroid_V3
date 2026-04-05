from __future__ import annotations

from datetime import UTC, datetime

from app.features.leveling.cog import TOKYO_TZ, current_tokyo_datetime


def test_current_tokyo_datetime_uses_jst_boundary() -> None:
    now = datetime(2026, 4, 30, 15, 0, tzinfo=UTC)

    converted = current_tokyo_datetime(now)

    assert converted.tzinfo == TOKYO_TZ
    assert (converted.year, converted.month, converted.day, converted.hour, converted.minute) == (2026, 5, 1, 0, 0)


def test_current_tokyo_datetime_preserves_same_month_in_jst() -> None:
    now = datetime(2026, 5, 1, 3, 0, tzinfo=UTC)

    converted = current_tokyo_datetime(now)

    assert (converted.year, converted.month, converted.day, converted.hour) == (2026, 5, 1, 12)
