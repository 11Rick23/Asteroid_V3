"""P3から呼べるメッセージ計上基盤。Discord受付・cooldown判定は接続しない。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.leveling_v2 import Event, EventChannel, EventPeriod, MessageReceipt
from app.features.leveling.domain.boosts import Boost, ShardAward, text_award
from app.features.leveling.domain.numbers import amount, identifier
from app.features.leveling.domain.periods import aware, periods_at

from .dto import AwardResult
from .power import add_power
from .storage import add_growth, event_result, lock_accounts, lock_periods
from .transaction import DuplicateOperation, Resolution


@dataclass(frozen=True)
class MessageAward:
    message_id: int
    user_id: int
    kind: str
    occurred_at: datetime
    recorded_at: datetime
    raw_xp: int
    channel_id: int | None = None
    source_bot_id: int | None = None
    boosts: tuple[Boost, ...] = ()
    role_ids: frozenset[int] = frozenset()
    calculation_version: str = "p1"
    outcome: str = "awarded"

    def __post_init__(self) -> None:
        identifier(self.message_id)
        identifier(self.user_id)
        amount(self.raw_xp)
        aware(self.occurred_at)
        aware(self.recorded_at)
        if self.kind not in ("text", "action"):
            raise ValueError("メッセージの種別が不正です")
        if self.channel_id is not None:
            identifier(self.channel_id)
        if self.kind == "action" and self.channel_id is not None:
            raise ValueError("アクションはチャンネルへ配分できません")
        if self.source_bot_id is not None:
            identifier(self.source_bot_id)
        if self.outcome not in ("awarded", "cooldown", "ineligible"):
            raise ValueError("処理結果が不正です")
        if not self.calculation_version or len(self.calculation_version) > 64:
            raise ValueError("計算バージョンが不正です")


async def find_message(session: AsyncSession, message_id: int, now: datetime) -> Resolution[AwardResult]:
    receipt = await session.get(MessageReceipt, message_id)
    if receipt is None or receipt.expires_at <= now:
        return Resolution(False)
    event = (await session.scalars(select(Event).where(Event.operation_key == receipt.operation_key))).one()
    return Resolution(True, await event_result(session, event))


async def apply_message(session: AsyncSession, request: MessageAward, coverage: datetime) -> AwardResult:
    # 早期重複検査はロックを取らない。競合は末尾のreceiptロック/UQでtx全体を戻す。
    existing = await find_message(session, request.message_id, request.recorded_at)
    if existing.found:
        raise DuplicateOperation()
    periods = await lock_periods(session, periods_at(request.occurred_at), coverage)
    account = (await lock_accounts(session, (request.user_id,)))[0]
    enabled = request.outcome == "awarded"
    shard = (
        text_award(request.raw_xp, request.boosts, request.role_ids, request.occurred_at)
        if enabled and request.kind == "text"
        else ShardAward(0, 0)
    )
    power = request.raw_xp if enabled else 0
    channels = ((request.channel_id, power),) if request.channel_id is not None else ()
    if shard.total:
        add_growth(account, text=shard.base, bonus=shard.bonus)
    await add_power(session, periods, request.user_id, request.kind, power, channels)
    await session.flush()
    receipt = (
        await session.scalars(
            select(MessageReceipt).where(MessageReceipt.message_id == request.message_id).with_for_update()
        )
    ).one_or_none()
    if receipt is not None and receipt.expires_at > request.recorded_at:
        raise DuplicateOperation()
    if receipt is not None:
        generation = receipt.generation + 1
        await session.execute(
            delete(Event).where(Event.operation_key == receipt.operation_key, Event.expires_at <= request.recorded_at)
        )
        await session.delete(receipt)
        await session.flush()
    else:
        delta = request.recorded_at.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC)
        generation = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
        identifier(generation)
    key = f"message:{request.message_id}:{generation}"
    expires = request.recorded_at + timedelta(days=90)
    event = Event(
        operation_key=key,
        user_id=request.user_id,
        kind=request.kind,
        occurred_at=request.occurred_at,
        recorded_at=request.recorded_at,
        expires_at=expires,
        raw_xp=request.raw_xp,
        base_shard=shard.base,
        bonus_shard=shard.bonus,
        power=power,
        source_message_id=request.message_id,
        source_bot_id=request.source_bot_id,
        status=request.outcome,
        calculation_version=request.calculation_version,
        calculation_inputs={
            "raw_xp": str(request.raw_xp),
            "role_ids": sorted(request.role_ids),
            "boost_ids": [boost.boost_id for boost in request.boosts],
        },
    )
    session.add(event)
    await session.flush()
    session.add_all(
        EventChannel(event_id=event.event_id, channel_id=channel, duration_us=0, allocated_power=value)
        for channel, value in channels
    )
    session.add_all(
        EventPeriod(
            event_id=event.event_id,
            period_id=p.period_id,
            accepted=p.status == "OPEN",
            reason="open" if p.status == "OPEN" else "finalized",
            accepted_power=power if p.status == "OPEN" else 0,
        )
        for p in periods
    )
    session.add(
        MessageReceipt(
            message_id=request.message_id,
            route=request.kind,
            generation=generation,
            operation_key=key,
            processed_at=request.recorded_at,
            expires_at=expires,
            outcome=request.outcome,
        )
    )
    await session.flush()
    return await event_result(session, event)
