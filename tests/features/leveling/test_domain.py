from __future__ import annotations

import pytest

from app.features.leveling.domain.math_calculation import (
    calculation_grade,
    calculation_prestige,
    calculation_shard,
    cumulative_grade_shard,
    next_grade_progress,
    shard_for_next_grade,
    total_shard_amount,
)


def test_calculates_next_grade():
    """次グレードに必要な shard は grade に応じた既存式で計算する。"""
    # Given / When / Then
    assert shard_for_next_grade(0) == 100
    assert shard_for_next_grade(1) == 155


def test_applies_shard_gain():
    """必要 shard を超える加算では grade を上げ、余剰 shard を保持する。"""
    # Given
    prestige = 0
    grade = 0
    shard = 90

    # When
    result = calculation_shard(prestige, grade, shard, 15)

    # Then
    assert result == (0, 1, 5, 1, 0)


def test_clamps_shard_loss():
    """現在値を超える shard 減算では prestige、grade、shard を 0 に戻す。"""
    # Given / When
    result = calculation_shard(1, 10, 50, -9999999)

    # Then
    assert result == (0, 0, 0, -10, -1)


def test_rejects_invalid_grade():
    """grade の増減結果が 0 から 49 の範囲外になる場合は拒否する。"""
    # Given / When / Then
    with pytest.raises(ValueError, match="0以上49以下"):
        calculation_grade(0, 49, 0, 1)


def test_calculates_progress():
    """次グレード進捗は整数パーセントと 9 区画のバーで返す。"""
    # Given / When
    percent, bar = next_grade_progress(0, 50)

    # Then
    assert percent == 50
    assert bar == "[■■■■■□□□□]"


def test_totals_shards():
    """総 shard は prestige、累積 grade、現在 shard の合計で返す。"""
    # Given / When
    total = total_shard_amount(1, 2, 3)

    # Then
    assert total == 268375 + cumulative_grade_shard(2) + 3


def test_calculates_prestige_cost():
    """prestige 増減は必要 shard 量も合わせて返す。"""
    # Given / When
    *_, used_shard = calculation_prestige(0, 0, 0, 1)

    # Then
    assert used_shard == 268375
