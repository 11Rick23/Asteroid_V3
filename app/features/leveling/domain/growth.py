"""現行成長式の独立実装。既存math_calculationの呼出し先は変更しない。"""

from __future__ import annotations

from dataclasses import dataclass

from .numbers import MAX_AMOUNT, amount, integer

PRESTIGE_REQUIRED_SHARD = 268375


def shard_for_next_grade(grade: int) -> int:
    integer(grade, maximum=49)
    return 5 * grade**2 + 50 * grade + 100


def cumulative_grade_shard(grade: int) -> int:
    integer(grade, maximum=50)
    return (2 * grade**3 + 27 * grade**2 + 91 * grade) * 5 // 6


@dataclass(frozen=True)
class Growth:
    prestige: int = 0
    grade: int = 0
    shard: int = 0

    def __post_init__(self) -> None:
        amount(self.prestige)
        integer(self.grade, maximum=49)
        integer(self.shard, maximum=shard_for_next_grade(self.grade) - 1)
        amount(self.total)

    @property
    def total(self) -> int:
        return self.prestige * PRESTIGE_REQUIRED_SHARD + cumulative_grade_shard(self.grade) + self.shard


@dataclass(frozen=True)
class GrowthChange:
    growth: Growth
    grade_change: int
    prestige_change: int
    requested_shard: int
    applied_shard: int


def from_total(total: int) -> Growth:
    amount(total)
    prestige, remainder = divmod(total, PRESTIGE_REQUIRED_SHARD)
    grade = 0
    while grade < 49 and remainder >= shard_for_next_grade(grade):
        remainder -= shard_for_next_grade(grade)
        grade += 1
    return Growth(prestige, grade, remainder)


def change_shard(current: Growth, delta: int) -> GrowthChange:
    integer(delta, minimum=-MAX_AMOUNT)
    result = from_total(max(0, current.total + delta))
    prestige_change = result.prestige - current.prestige
    # 減算時も現行が返す再計算の昇格回数を維持する（純粋なgrade差とは異なる）。
    grade_change = result.grade - current.grade + (50 * (prestige_change if delta >= 0 else result.prestige))
    return GrowthChange(result, grade_change, prestige_change, delta, result.total - current.total)


def change_grade(current: Growth, delta: int) -> GrowthChange:
    integer(delta, minimum=-49, maximum=49)
    target = integer(current.grade + delta, maximum=49)
    return change_shard(current, cumulative_grade_shard(target) - cumulative_grade_shard(current.grade))


def change_prestige(current: Growth, delta: int) -> GrowthChange:
    integer(delta, minimum=-MAX_AMOUNT)
    return change_shard(current, delta * PRESTIGE_REQUIRED_SHARD)
