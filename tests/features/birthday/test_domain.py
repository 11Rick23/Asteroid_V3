from __future__ import annotations

from datetime import date

import pytest

from app.features.birthday.cog import DEFAULT_YEAR, convert_date, validate_date


def test_validates_date():
    """存在する月日だけを誕生日として受け付ける。"""
    # 機能要件：存在する月日だけを誕生日として受け付ける。
    # Given / When / Then
    assert validate_date(2, 29) is True
    assert validate_date(2, 30) is False
    assert validate_date(13, 1) is False


def test_converts_near_date():
    """今日、明日、明後日の誕生日は相対表現に変換する。"""
    # 機能要件：直近 2 日以内の誕生日は相対表現で表示する。
    # Given
    today = date(2026, 6, 23)

    # When / Then
    assert convert_date(today, date(DEFAULT_YEAR, 6, 23)) == "今日"
    assert convert_date(today, date(DEFAULT_YEAR, 6, 24)) == "明日"
    assert convert_date(today, date(DEFAULT_YEAR, 6, 25)) == "明後日"


def test_converts_next_year():
    """今年過ぎた誕生日は翌年の日付として表示する。"""
    # 機能要件：今年過ぎた誕生日は次回到来する翌年の日付で表示する。
    # Given
    today = date(2026, 12, 31)

    # When
    label = convert_date(today, date(DEFAULT_YEAR, 1, 3))

    # Then
    assert label == "2027年01月03日"


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 1, 1), "2026年02月28日"),
        (date(2026, 2, 27), "明日"),
        (date(2026, 2, 28), "今日"),
        (date(2026, 3, 1), "2027年02月28日"),
        (date(2027, 3, 1), "2028年02月29日"),
        (date(2028, 2, 28), "明日"),
        (date(2028, 2, 29), "今日"),
        (date(2028, 3, 1), "2029年02月28日"),
    ],
)
def test_converts_leap_birthday(today, expected):
    """2月29日の誕生日は平年に2月28日、閏年に2月29日として次回の日付を表示する。"""
    # 機能要件：誕生日の告知と同じ日付で、今日・明日・翌年の誕生日を表示する。
    # Given / When / Then
    assert convert_date(today, date(DEFAULT_YEAR, 2, 29)) == expected
