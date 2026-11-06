from __future__ import annotations

from datetime import datetime

import pytest

from app.features.leveling.domain.periods import JST
from app.features.leveling.domain.rankings import MonthlyResult, rank_scores, top1_qualification


def month(year: int, number: int) -> datetime:
    return datetime(year, number, 1, tzinfo=JST)


def test_ties_and_zero():
    """同点は1,1,3順位となり、0パワーは除外し同率10位全員を含める。"""
    # 機能要件：RANK方式を用い、対象者の在籍状況で繰り上げない。
    # Given
    scores = {1: 100, 2: 100, 3: 90, 4: 0}
    # When
    result = rank_scores(scores)
    # Then
    assert [(r.subject_id, r.rank) for r in result] == [(1, 1), (2, 1), (3, 3)]
    scores = {i: 100 - i for i in range(1, 10)} | dict.fromkeys(range(10, 40), 1)
    assert len([row for row in rank_scores(scores) if row.rank <= 10]) == 39
    assert rank_scores({1: 0}) == ()


@pytest.mark.parametrize(
    "ranks,expected,consecutive",
    [
        ([1, 1, 1], True, 3),
        ([1, 1, 2], False, 0),
        ([1, None, 1], False, 1),
        ([1, 1, 1, 1], True, 4),
        ([1, 1, 1, 2], True, 0),
    ],
)
def test_three_months(ranks: list[int | None], expected: bool, consecutive: int):
    """隣接3暦月のTOP1で資格を得て、その後順位が下がっても過去資格を保持する。"""
    # 機能要件：空月は連続を切り、4ヶ月目でも資格を重複生成しない。
    # Given
    results = [
        MonthlyResult(month(2026, index + 1), 100 if rank is not None else 0, rank) for index, rank in enumerate(ranks)
    ]
    # When
    result = top1_qualification(results, month(2026, 1), month(2026, len(ranks)))
    # Then
    assert result.qualified is expected
    assert result.consecutive == consecutive
    assert result.first_earned_month == (month(2026, 3) if expected else None)


def test_tied_top1_year_boundary():
    """同率1位も年を跨ぐ3ヶ月連続の資格対象となる。"""
    # 機能要件：同率TOP1の全員が同じ連続資格を得る。
    # Given
    months = [month(2026, 11), month(2026, 12), month(2027, 1)]
    ranking = rank_scores({1: 100, 2: 100})
    # When / Then
    for row in ranking:
        result = top1_qualification([MonthlyResult(m, row.score, row.rank) for m in months], months[0], months[-1])
        assert result.qualified and result.consecutive == 3


def test_missing_migration_and_correction():
    """欠落月と移行前履歴は連続に含めず、訂正後も別の3ヶ月窓があれば資格が残る。"""
    # 機能要件：移行月以降の全ての3ヶ月窓を再判定する。
    # Given
    results = [MonthlyResult(month(2026, m), 1, 1) for m in [1, 2, 3, 5, 6, 7]]
    # When / Then
    assert not top1_qualification(results, month(2026, 2), month(2026, 3)).qualified
    assert top1_qualification(results, month(2026, 1), month(2026, 4)).consecutive == 0
    corrected = [r for r in results if r.month != month(2026, 2)]
    result = top1_qualification(corrected, month(2026, 1), month(2026, 7))
    assert result.first_earned_month == month(2026, 7)
    assert not top1_qualification(corrected, month(2026, 1), month(2026, 6)).qualified


def test_invalid_ranking():
    """0パワーの順位付け・負値・月重複・月初以外を拒否する。"""
    # 非機能要件：不整合な確定月入力で資格を作らない。
    # Given
    start = month(2026, 1)
    record = MonthlyResult(start, 1, 1)
    # When / Then
    with pytest.raises(ValueError):
        rank_scores({1: -1})
    with pytest.raises(ValueError):
        MonthlyResult(start, 0, 1)
    with pytest.raises(ValueError):
        MonthlyResult(start, 1, None)
    with pytest.raises(ValueError):
        MonthlyResult(datetime(2026, 1, 2, tzinfo=JST), 1, 1)
    with pytest.raises(ValueError):
        top1_qualification([record, record], start, start)
