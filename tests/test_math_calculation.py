from __future__ import annotations

from app.features.leveling.domain.math_calculation import (
    calculation_grade,
    calculation_prestige,
    calculation_shard,
    next_grade_progress,
    total_shard_amount,
)


def test_calculation_shard_levels_up() -> None:
    prestige, grade, shard, grade_up_amount, prestige_amount = calculation_shard(0, 0, 0, 100)
    assert prestige == 0
    assert grade == 1
    assert shard == 0
    assert grade_up_amount == 1
    assert prestige_amount == 0


def test_calculation_grade_returns_added_shard() -> None:
    prestige, grade, shard, grade_up_amount, prestige_amount, added_shard = calculation_grade(0, 0, 0, 2)
    assert prestige == 0
    assert grade == 2
    assert grade_up_amount == 2
    assert prestige_amount == 0
    assert added_shard > 0
    assert shard == 0


def test_calculation_prestige_increases_prestige() -> None:
    prestige, grade, shard, grade_up_amount, prestige_amount, added_shard = calculation_prestige(0, 0, 0, 1)
    assert prestige == 1
    assert grade == 0
    assert prestige_amount == 1
    assert grade_up_amount == 50
    assert added_shard == 268375
    assert shard == 0


def test_progress_and_total_helpers() -> None:
    progress, progress_bar = next_grade_progress(1, 77)
    assert isinstance(progress, int)
    assert progress_bar.startswith("[")
    assert total_shard_amount(1, 2, 3) > 0
