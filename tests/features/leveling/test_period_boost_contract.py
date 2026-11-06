from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext

import pytest

from app.features.leveling.domain.boosts import Boost, rate_at, text_award
from app.features.leveling.domain.numbers import MAX_AMOUNT, coefficient
from app.features.leveling.domain.periods import JST, Period, PeriodKind, period_at, periods_at
from app.features.leveling.domain.voice_time import boosted_segments


@pytest.mark.parametrize(
    "at,day,week,month",
    [
        ("2026-12-31T15:00:00+00:00", "2027-01-01", "2026-12-28", "2027-01-01"),
        ("2024-02-29T23:59:59+09:00", "2024-02-29", "2024-02-26", "2024-02-01"),
        ("2026-10-31T23:59:59+09:00", "2026-10-31", "2026-10-26", "2026-10-01"),
        ("2026-11-02T00:00:00+09:00", "2026-11-02", "2026-11-02", "2026-11-01"),
    ],
)
def test_calendar(at: str, day: str, week: str, month: str):
    """UTC入力をJSTの暦日・月曜週・暦月へ帰属させる。"""
    # 機能要件：閏日・年末・週月境界を半開区間で扱う。
    # Given / When
    periods = periods_at(datetime.fromisoformat(at))
    # Then
    assert [p.start.date().isoformat() for p in periods] == [day, week, month]
    for period in periods:
        assert period.contains(period.start)
        assert period.contains(period.end - timedelta(microseconds=1))
        assert not period.contains(period.end)
        assert not period.has_ended(period.end - timedelta(microseconds=1))
        assert period.has_ended(period.end)
        assert period_at(period.start.astimezone(UTC), period.kind) == period


def test_invalid_period():
    """タイムゾーンなしや暦境界に一致しない期間は拒否する。"""
    # 非機能要件：期間所属の曖昧な入力を受け付けない。
    # Given / When / Then
    with pytest.raises(ValueError):
        period_at(datetime(2026, 1, 1), PeriodKind.DAY)
    with pytest.raises(ValueError):
        Period(PeriodKind.MONTH, datetime(2026, 1, 2, tzinfo=JST), datetime(2026, 2, 1, tzinfo=JST))


def test_boost_overlap():
    """同一ロールの複数予約と別ロールの率を加算し、終了・取消時刻は除外する。"""
    # 機能要件：加算率は開始を含み終了を含まない。
    # Given
    start = datetime(2026, 1, 1, tzinfo=JST)
    end = start + timedelta(seconds=30)
    boosts = [
        Boost(1, 10, 50, start, end),
        Boost(2, 10, 100, start),
        Boost(3, 20, 25, start, cancelled_at=end),
        Boost(4, 30, 999, start),
    ]
    # When / Then
    assert rate_at(boosts, {10, 20}, start - timedelta(microseconds=1)) == 0
    assert rate_at(boosts, {10, 20}, start) == 175
    assert rate_at(boosts, {10, 20}, end) == 100
    assert text_award(3, boosts, {10, 20}, start).total == 8
    assert text_award(3, boosts, {10, 20}, end).bonus == 3
    parts = boosted_segments(start, end + timedelta(seconds=30), 1, boosts, {10, 20})
    assert [(p.duration, p.rate_percent) for p in parts] == [(30_000_000, 175), (30_000_000, 100)]


def test_large_boost_precision():
    """倍率の業務上限を作らず、低いDecimal精度でも整数の最終切捨てを守る。"""
    # 非機能要件：Decimalコンテキストや途中丸めに依存しない。
    # Given
    start = datetime(2026, 1, 1, tzinfo=JST)
    boosts = [Boost(1, 1, MAX_AMOUNT, start), Boost(2, 1, MAX_AMOUNT, start)]
    # When / Then
    with localcontext() as context:
        context.prec = 2
        assert text_award(1, boosts, {1}, start).total == (100 + 2 * MAX_AMOUNT) // 100
        assert coefficient(Decimal("0.30000000000000000000001")).numerator == 30000000000000000000001
    with pytest.raises(ValueError):
        text_award(100, boosts, {1}, start)


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-0.1")])
def test_invalid_coefficient(value: Decimal):
    """非有限・負のVC調整係数を拒否する。"""
    # 非機能要件：無効な係数で数量を生成しない。
    # Given / When / Then
    with pytest.raises(ValueError):
        coefficient(value)


def test_invalid_boost():
    """終了逆転と重複予約IDを拒否する。"""
    # 非機能要件：同じ予約を二重に倍率へ加算しない。
    # Given
    start = datetime(2026, 1, 1, tzinfo=JST)
    boost = Boost(1, 1, 100, start)
    # When / Then
    with pytest.raises(ValueError):
        Boost(1, 1, 100, start, start)
    with pytest.raises(ValueError):
        rate_at([boost, boost], {1}, start)
