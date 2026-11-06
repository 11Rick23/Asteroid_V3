from __future__ import annotations

from typing import cast

import pytest

from app.features.leveling.domain import growth
from app.features.leveling.domain import math_calculation as old
from app.features.leveling.domain.numbers import MAX_AMOUNT, amount, total_amount


@pytest.mark.parametrize("grade", range(50))
@pytest.mark.parametrize("prestige", [0, 3])
@pytest.mark.parametrize("delta", [-900000, -1, 0, 1, 900000])
def test_matches_legacy(grade: int, prestige: int, delta: int):
    """全グレードで加減算後の成長値と昇格回数が現行実装に一致する。"""
    # 機能要件：既存成長式と返却する昇格回数を維持する。
    # Given
    shard = old.shard_for_next_grade(grade) - 1
    current = growth.Growth(prestige, grade, shard)
    # When
    result = growth.change_shard(current, delta)
    # Then
    assert (
        result.growth.prestige,
        result.growth.grade,
        result.growth.shard,
        result.grade_change,
        result.prestige_change,
    ) == old.calculation_shard(prestige, grade, shard, delta)
    assert growth.shard_for_next_grade(grade) == old.shard_for_next_grade(grade)
    assert growth.cumulative_grade_shard(grade) == old.cumulative_grade_shard(grade)
    assert result.applied_shard == result.growth.total - current.total


@pytest.mark.parametrize("delta", [-268376, -268375, -1, 0, 1, 268375, 268376])
def test_prestige_boundary(delta: int):
    """グレード49の最後の1シャードを越えるとプレステージへ移行する。"""
    # 機能要件：プレステージ境界前後を現行と同じ値に正規化する。
    # Given
    current = growth.from_total(268374)
    # When
    result = growth.change_shard(current, delta)
    # Then
    assert (result.growth.prestige, result.growth.grade, result.growth.shard) == old.calculation_shard(
        current.prestige, current.grade, current.shard, delta
    )[:3]
    if delta == 1:
        assert result.growth == growth.Growth(1, 0, 0)


@pytest.mark.parametrize("delta", [-3, -1, 0, 1, 3])
def test_grade_prestige_changes(delta: int):
    """管理者用グレード・プレステージ増減も現行の変換式に一致する。"""
    # 機能要件：成長段階からのシャード換算を維持する。
    # Given
    current = growth.Growth(2, 20, 99)
    # When / Then
    for new_fn, old_fn in (
        (growth.change_grade, old.calculation_grade),
        (growth.change_prestige, old.calculation_prestige),
    ):
        result = new_fn(current, delta)
        assert (
            result.growth.prestige,
            result.growth.grade,
            result.growth.shard,
            result.grade_change,
            result.prestige_change,
            abs(result.requested_shard),
        ) == old_fn(2, 20, 99, delta)


def test_huge_growth():
    """65桁の最大値も周回回数に比例する反復なしに計算し、過大減算は0にする。"""
    # 非機能要件：大量XPで処理量が増大せず、範囲超過を隠さない。
    # Given / When
    current = growth.change_shard(growth.Growth(), MAX_AMOUNT).growth
    # Then
    assert current.total == MAX_AMOUNT
    assert growth.change_shard(current, -MAX_AMOUNT).growth == growth.Growth()
    assert growth.change_shard(growth.Growth(1), -MAX_AMOUNT).growth == growth.Growth()
    with pytest.raises(ValueError):
        growth.change_shard(current, 1)
    with pytest.raises(ValueError):
        total_amount(MAX_AMOUNT, 1)


@pytest.mark.parametrize("value", [-1, MAX_AMOUNT + 1, True, 1.5, float("nan"), float("inf"), "1"])
def test_invalid_amount(value: object):
    """負値・小数・非有限値・真偽値・文字列・範囲超過は数量として拒否する。"""
    # 非機能要件：不正入力を丸めや暗黙変換で受け付けない。
    # Given / When / Then
    with pytest.raises(ValueError):
        amount(cast(int, value))


@pytest.mark.parametrize("values", [(0, -1, 0), (0, 50, 0), (-1, 0, 0), (0, 0, 100)])
def test_invalid_growth(values: tuple[int, int, int]):
    """不正な成長状態を自動修復せず拒否する。"""
    # 非機能要件：DR05の不整合を黙って正規化しない。
    # Given / When / Then
    with pytest.raises(ValueError):
        growth.Growth(*values)
