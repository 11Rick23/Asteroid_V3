"""JST暦の半開区間。現在時刻は必ず呼出し側から渡す。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


class PeriodKind(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


def aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("タイムゾーン付き日時を指定してください")
    return value.astimezone(JST)


def next_month(start: datetime) -> datetime:
    start = aware(start)
    return start.replace(year=start.year + (start.month == 12), month=start.month % 12 + 1, day=1)


def _bounds(at: datetime, kind: PeriodKind) -> tuple[datetime, datetime]:
    if not isinstance(kind, PeriodKind):
        raise ValueError("期間種別が不正です")
    start = aware(at).replace(hour=0, minute=0, second=0, microsecond=0)
    if kind == PeriodKind.DAY:
        return start, start + timedelta(days=1)
    if kind == PeriodKind.WEEK:
        start -= timedelta(days=start.weekday())
        return start, start + timedelta(days=7)
    start = start.replace(day=1)
    return start, next_month(start)


@dataclass(frozen=True)
class Period:
    kind: PeriodKind
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        start, end = aware(self.start), aware(self.end)
        if (start, end) != _bounds(start, self.kind):
            raise ValueError("期間はJSTの暦境界に一致する必要があります")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)

    def contains(self, at: datetime) -> bool:
        return self.start <= aware(at) < self.end

    def has_ended(self, now: datetime) -> bool:
        return aware(now) >= self.end


def period_at(at: datetime, kind: PeriodKind) -> Period:
    return Period(kind, *_bounds(at, kind))


def periods_at(at: datetime) -> tuple[Period, ...]:
    return tuple(period_at(at, kind) for kind in PeriodKind)


def next_boundary(at: datetime) -> datetime:
    return min(period.end for period in periods_at(at))


def duration_us(start: datetime, end: datetime) -> int:
    delta = aware(end) - aware(start)
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
