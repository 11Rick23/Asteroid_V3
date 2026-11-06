"""内部txヘルパー。commitせず、既定の階層順で呼出し元が組み立てる。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.leveling_v2 import Account, Event, EventPeriod, PeriodRow, VoicePending, VoiceState
from app.database.models.leveling_v2.base import LevelingBase
from app.features.leveling.domain.growth import Growth, from_total
from app.features.leveling.domain.numbers import identifier, total_amount
from app.features.leveling.domain.periods import Period, PeriodKind

from .dto import AccountData, AwardResult


async def ensure(session: AsyncSession, model: type[LevelingBase], values: dict[str, object], key: str) -> None:
    statement = insert(model).values(**values)
    await session.execute(statement.on_duplicate_key_update(**{key: getattr(model, key)}))


async def lock_periods(session: AsyncSession, periods: tuple[Period, ...], coverage: datetime) -> list[PeriodRow]:
    order = {kind: index for index, kind in enumerate(PeriodKind)}
    result: list[PeriodRow] = []
    for period in sorted(set(periods), key=lambda p: (p.start, order[p.kind])):
        await ensure(
            session,
            PeriodRow,
            {
                "kind": period.kind.value,
                "start_at": period.start,
                "end_at": period.end,
                "status": "OPEN",
                "current_revision": 0,
                "coverage_start_at": coverage,
            },
            "period_id",
        )
        row = (
            await session.scalars(
                select(PeriodRow)
                .where(
                    PeriodRow.kind == period.kind.value,
                    PeriodRow.start_at == period.start,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).one()
        result.append(row)
    return result


async def lock_accounts(session: AsyncSession, users: tuple[int, ...]) -> list[Account]:
    result: list[Account] = []
    for user in sorted(set(users)):
        identifier(user)
        await ensure(session, Account, {"user_id": user}, "user_id")
        result.append((await session.scalars(select(Account).where(Account.user_id == user).with_for_update())).one())
    return result


async def lock_states(session: AsyncSession, users: tuple[int, ...]) -> list[VoiceState]:
    if not users:
        return []
    return list(
        await session.scalars(
            select(VoiceState).where(VoiceState.user_id.in_(users)).order_by(VoiceState.user_id).with_for_update()
        )
    )


async def lock_pending(session: AsyncSession, users: tuple[int, ...]) -> list[VoicePending]:
    if not users:
        return []
    return list(
        await session.scalars(
            select(VoicePending)
            .where(VoicePending.user_id.in_(users))
            .order_by(VoicePending.user_id, VoicePending.month_period_id, VoicePending.origin)
            .with_for_update()
        )
    )


def account_data(row: Account) -> AccountData:
    growth = Growth(row.prestige, row.grade, row.shard)
    if growth.total != total_amount(row.text_shard, row.voice_shard, row.bonus_shard):
        raise ValueError("恒常残高と成長値が一致しません")
    return AccountData(row.user_id, row.text_shard, row.voice_shard, row.bonus_shard, growth, row.version)


def add_growth(row: Account, *, text: int = 0, voice: int = 0, bonus: int = 0) -> None:
    account_data(row)
    text_total = total_amount(row.text_shard, text)
    voice_total = total_amount(row.voice_shard, voice)
    bonus_total = total_amount(row.bonus_shard, bonus)
    growth = from_total(total_amount(text_total, voice_total, bonus_total))
    row.text_shard, row.voice_shard, row.bonus_shard = text_total, voice_total, bonus_total
    row.prestige, row.grade, row.shard = growth.prestige, growth.grade, growth.shard
    row.version += 1


async def event_result(session: AsyncSession, event: Event) -> AwardResult:
    periods = list(
        await session.scalars(
            select(EventPeriod).where(EventPeriod.event_id == event.event_id).order_by(EventPeriod.period_id)
        )
    )
    return AwardResult(
        event.operation_key,
        event.event_id,
        event.user_id,
        event.base_shard,
        event.bonus_shard,
        event.power,
        tuple(p.period_id for p in periods if p.accepted),
        tuple(p.period_id for p in periods if not p.accepted),
    )
