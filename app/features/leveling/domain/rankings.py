from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from .numbers import amount, identifier, integer
from .periods import PeriodKind, aware, period_at


@dataclass(frozen=True)
class RankedScore:
    subject_id: int
    score: int
    rank: int

    def __post_init__(self) -> None:
        identifier(self.subject_id)
        integer(self.score, minimum=1)
        integer(self.rank, minimum=1)


def rank_scores(scores: Mapping[int, int]) -> tuple[RankedScore, ...]:
    """0を除外してRANK相当を計算する。所属・在籍状態では繰り上げない。"""
    for subject_id, score in scores.items():
        identifier(subject_id)
        amount(score)
    ordered = sorted(((key, value) for key, value in scores.items() if value), key=lambda row: (-row[1], row[0]))
    result: list[RankedScore] = []
    previous = None
    rank = 0
    for position, (subject_id, score) in enumerate(ordered, 1):
        if score != previous:
            rank = position
        result.append(RankedScore(subject_id, score, rank))
        previous = score
    return tuple(result)


@dataclass(frozen=True)
class MonthlyResult:
    month: datetime
    score: int
    rank: int | None

    def __post_init__(self) -> None:
        month = aware(self.month)
        if month != period_at(month, PeriodKind.MONTH).start:
            raise ValueError("月はJST月初で指定してください")
        object.__setattr__(self, "month", month)
        amount(self.score)
        if self.rank is not None:
            integer(self.rank, minimum=1)
        if (self.score == 0) != (self.rank is None):
            raise ValueError("0パワーは順位なし、正のパワーは順位が必要です")


@dataclass(frozen=True)
class Top1Qualification:
    consecutive: int
    first_earned_month: datetime | None

    @property
    def qualified(self) -> bool:
        return self.first_earned_month is not None


def top1_qualification(
    results: Sequence[MonthlyResult],
    migration_month: datetime,
    through_month: datetime,
) -> Top1Qualification:
    """確定済みの1ユーザー分の履歴を受け取り、移行月以降の全窓を判定する。"""
    migration_month, through_month = aware(migration_month), aware(through_month)
    for month in (migration_month, through_month):
        if month != period_at(month, PeriodKind.MONTH).start:
            raise ValueError("判定月はJST月初で指定してください")
    if migration_month > through_month:
        raise ValueError("判定終了月は移行月以降にしてください")
    if len({result.month for result in results}) != len(results):
        raise ValueError("月間結果が重複しています")
    streak = 0
    previous_index: int | None = None
    earned = None
    for result in sorted(results, key=lambda result: result.month):
        if not migration_month <= result.month <= through_month:
            continue
        index = result.month.year * 12 + result.month.month
        if previous_index != index - 1:
            streak = 0
        streak = streak + 1 if result.rank == 1 else 0
        if streak >= 3 and earned is None:
            earned = result.month
        previous_index = index
    if previous_index != through_month.year * 12 + through_month.month:
        streak = 0
    return Top1Qualification(streak, earned)
