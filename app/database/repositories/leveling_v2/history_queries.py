"""保存済み履歴の読み取り境界。Discord認可・表示は呼出し側が担当する。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import Claim, Event, EventChannel, MonthlyQualification, Operation
from app.features.leveling.domain.numbers import identifier, integer
from app.features.leveling.domain.periods import aware

from .claims import claim_data
from .dto import ClaimResult


@dataclass(frozen=True)
class HistoryCursor:
    at: datetime
    event_id: int


@dataclass(frozen=True)
class EventData:
    event_id: int
    operation_key: str
    user_id: int
    kind: str
    occurred_at: datetime
    recorded_at: datetime
    raw_xp: int
    base_shard: int
    bonus_shard: int
    power: int
    status: str


@dataclass(frozen=True)
class HistoryPage:
    events: tuple[EventData, ...]
    next_cursor: HistoryCursor | None


@dataclass(frozen=True)
class OperationData:
    operation_key: str
    kind: str
    actor_id: int
    status: str
    before: dict[str, object]
    after: dict[str, object]
    completed_at: datetime | None


@dataclass(frozen=True)
class QualificationData:
    month_period_id: int
    user_id: int
    revision: int
    is_top1: bool
    is_top10: bool
    consecutive_top1: int


class HistoryRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def events(
        self,
        start: datetime,
        end: datetime,
        *,
        as_of: datetime,
        user_id: int | None = None,
        channel_id: int | None = None,
        kind: str | None = None,
        bonus_only: bool = False,
        time_basis: str = "occurred",
        after: HistoryCursor | None = None,
        limit: int = 50,
    ) -> HistoryPage:
        for at in (start, end, as_of):
            aware(at)
        if not start < end <= start + timedelta(days=90):
            raise ValueError("履歴検索は正の90日以内の窓で指定してください")
        for value in (user_id, channel_id):
            if value is not None:
                identifier(value)
        integer(limit, minimum=1, maximum=1000)
        if time_basis not in ("occurred", "recorded") or type(bonus_only) is not bool:
            raise ValueError("履歴検索条件が不正です")
        if kind is not None and kind not in ("text", "voice", "action", "admin", "import", "claim"):
            raise ValueError("履歴種別が不正です")
        clock = Event.occurred_at if time_basis == "occurred" else Event.recorded_at
        query = select(Event).where(clock >= start, clock < end, Event.expires_at > as_of, Event.recorded_at <= as_of)
        if user_id is not None:
            query = query.where(Event.user_id == user_id)
        if channel_id is not None:
            query = query.where(
                exists().where(EventChannel.event_id == Event.event_id, EventChannel.channel_id == channel_id)
            )
        if kind is not None:
            query = query.where(Event.kind == kind)
        if bonus_only:
            query = query.where(Event.bonus_shard > 0)
        if after is not None:
            aware(after.at)
            identifier(after.event_id)
            query = query.where(or_(clock > after.at, and_(clock == after.at, Event.event_id > after.event_id)))
        async with self.sessions() as session:
            rows = list(await session.scalars(query.order_by(clock, Event.event_id).limit(limit + 1)))
            chosen = rows[:limit]
            events = tuple(
                EventData(
                    row.event_id,
                    row.operation_key,
                    row.user_id,
                    row.kind,
                    row.occurred_at,
                    row.recorded_at,
                    row.raw_xp,
                    row.base_shard,
                    row.bonus_shard,
                    row.power,
                    row.status,
                )
                for row in chosen
            )
            last = chosen[-1] if chosen else None
            cursor = (
                HistoryCursor(last.occurred_at if time_basis == "occurred" else last.recorded_at, last.event_id)
                if len(rows) > limit and last is not None
                else None
            )
            return HistoryPage(events, cursor)

    async def claim(self, operation_key: str) -> ClaimResult | None:
        async with self.sessions() as session:
            row = (await session.scalars(select(Claim).where(Claim.operation_key == operation_key))).one_or_none()
            return None if row is None else claim_data(row)

    async def operation(self, operation_key: str) -> OperationData | None:
        async with self.sessions() as session:
            row = await session.get(Operation, operation_key)
            return (
                None
                if row is None
                else OperationData(
                    row.operation_key,
                    row.kind,
                    row.actor_id,
                    row.status,
                    deepcopy(row.before_values),
                    deepcopy(row.after_values),
                    row.completed_at,
                )
            )

    async def qualification(self, month_period_id: int, user_id: int) -> QualificationData | None:
        identifier(month_period_id)
        identifier(user_id)
        async with self.sessions() as session:
            row = await session.get(MonthlyQualification, (month_period_id, user_id))
            return (
                None
                if row is None
                else QualificationData(
                    row.month_period_id,
                    row.user_id,
                    row.ranking_revision,
                    row.is_top1,
                    row.is_top10,
                    row.consecutive_top1,
                )
            )
