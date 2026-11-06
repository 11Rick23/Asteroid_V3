from __future__ import annotations

from collections.abc import Sequence, Set
from dataclasses import dataclass
from datetime import datetime

from .numbers import amount, identifier
from .periods import aware


@dataclass(frozen=True)
class Boost:
    boost_id: int
    role_id: int
    rate_percent: int
    start: datetime
    end: datetime | None = None
    cancelled_at: datetime | None = None

    def __post_init__(self) -> None:
        identifier(self.boost_id)
        identifier(self.role_id)
        amount(self.rate_percent)
        object.__setattr__(self, "start", aware(self.start))
        if self.end is not None:
            object.__setattr__(self, "end", aware(self.end))
            if self.end <= self.start:
                raise ValueError("予約終了は開始より後にしてください")
        if self.cancelled_at is not None:
            object.__setattr__(self, "cancelled_at", aware(self.cancelled_at))

    def active_at(self, at: datetime) -> bool:
        at = aware(at)
        return (
            self.start <= at
            and (self.end is None or at < self.end)
            and (self.cancelled_at is None or at < self.cancelled_at)
        )


def validate_boosts(boosts: Sequence[Boost]) -> None:
    if len({boost.boost_id for boost in boosts}) != len(boosts):
        raise ValueError("ブーストIDが重複しています")


def rate_at(boosts: Sequence[Boost], role_ids: Set[int], at: datetime) -> int:
    validate_boosts(boosts)
    aware(at)
    for role_id in role_ids:
        identifier(role_id)
    # 総率は中間値。各予約の格納範囲と最終付与量だけを検査する。
    return sum(boost.rate_percent for boost in boosts if boost.role_id in role_ids and boost.active_at(at))


@dataclass(frozen=True)
class ShardAward:
    base: int
    bonus: int

    def __post_init__(self) -> None:
        amount(self.base)
        amount(self.bonus)
        amount(self.total)

    @property
    def total(self) -> int:
        return self.base + self.bonus


def text_award(base: int, boosts: Sequence[Boost], role_ids: Set[int], at: datetime) -> ShardAward:
    amount(base)
    total = amount(base * (100 + rate_at(boosts, role_ids, at)) // 100)
    return ShardAward(base, total - base)
