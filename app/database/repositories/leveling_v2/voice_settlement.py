"""P1の付与単位と保存済み乱数を使用する原子的VC精算。Discord接続は持たない。"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.leveling_v2 import Event, EventChannel, EventPeriod, VoiceGrant, VoicePending
from app.features.leveling.domain.numbers import total_amount
from app.features.leveling.domain.periods import PeriodKind
from app.features.leveling.domain.voice_awards import calculate_voice_award
from app.features.leveling.domain.voice_limits import VoiceLimits
from app.features.leveling.domain.voice_time import take_voice_unit

from .claims import ClaimRequest, claim_locked
from .dto import AwardResult
from .power import add_power
from .storage import ensure, event_result, lock_accounts, lock_pending, lock_periods, lock_states
from .transaction import DuplicateOperation, Resolution, VersionConflict
from .voice_consumption import consume
from .voice_request import VoiceSettlement
from .voice_state import segment_data, segment_rows


async def find_grant(session: AsyncSession, request: VoiceSettlement) -> Resolution[AwardResult]:
    grant = await session.get(VoiceGrant, (request.user_id, request.grant_seq))
    if grant is None:
        return Resolution(False)
    if grant.operation_key != request.operation_key:
        raise VersionConflict("付与seqは別epochで確定済みです")
    event = (await session.scalars(select(Event).where(Event.operation_key == grant.operation_key))).one_or_none()
    if event is None:
        raise VersionConflict("付与済みですが詳細履歴の保持期間を過ぎています")
    return Resolution(True, await event_result(session, event))


async def settle_voice(session: AsyncSession, request: VoiceSettlement, coverage: datetime) -> AwardResult:
    if (await find_grant(session, request)).found:
        raise DuplicateOperation()
    # ロック前の見積りでperiod集合を固定する。state取得後に上位periodへ戻らない。
    planned = take_voice_unit(
        tuple(segment_data(row) for row in await segment_rows(session, request.user_id)), request.through
    )
    if planned.unit is None:
        raise ValueError("精算可能なVC単位がありません")
    periods = await lock_periods(session, planned.unit.periods, coverage)
    account = (await lock_accounts(session, (request.user_id,)))[0]
    states = await lock_states(session, (request.user_id,))
    if not states:
        raise VersionConflict("計測状態が存在しません")
    state = states[0]
    if (
        state.checkpoint_version != request.expected_version
        or state.measurement_epoch != request.measurement_epoch
        or state.next_grant_seq != request.grant_seq
        or state.prepared_grant_seq != request.grant_seq
        or state.prepared_random is None
    ):
        # 他sessionのcommitを待った場合は最新結果を別txで再照会する。
        if state.next_grant_seq > request.grant_seq:
            raise DuplicateOperation()
        raise VersionConflict("付与計画のversion・epoch・seqが一致しません")
    rows = await segment_rows(session, request.user_id, lock=True)
    step = take_voice_unit(tuple(segment_data(row) for row in rows), request.through)
    if step != planned or step.unit is None:
        raise VersionConflict("保存区間が計画から変わっています")
    unit = step.unit
    month = next(period for period in periods if period.kind == "month")
    await ensure(
        session,
        VoicePending,
        {
            "user_id": request.user_id,
            "month_period_id": month.period_id,
            "origin": "native",
        },
        "user_id",
    )
    pending = await lock_pending(session, (request.user_id,))
    target = next(row for row in pending if row.month_period_id == month.period_id and row.origin == "native")
    limits = VoiceLimits(
        total_amount(*(total_amount(row.voice_shard, row.bonus_shard) for row in pending)),
        total_amount(*(row.power_meter for row in pending)),
        request.shard_limit,
        request.power_limit,
    )
    raw_xp = state.prepared_random
    award = calculate_voice_award(
        unit,
        raw_xp,
        limits,
        frozenset(PeriodKind(p.kind) for p in periods if p.status == "OPEN"),
        adjustment=request.adjustment,
    )
    target.voice_shard = total_amount(target.voice_shard, award.shard.base)
    target.bonus_shard = total_amount(target.bonus_shard, award.shard.bonus)
    target.power_meter = total_amount(target.power_meter, award.power)
    target.version += 1
    await consume(session, state, rows, step, request.next_random)
    await add_power(session, periods, request.user_id, "voice", award.power, award.channel_power)
    event = Event(
        operation_key=request.operation_key,
        user_id=request.user_id,
        kind="voice",
        occurred_at=unit.settled_at,
        interval_start=unit.segments[0].start,
        interval_end=unit.segments[-1].end,
        recorded_at=request.recorded_at,
        expires_at=request.recorded_at + timedelta(days=90),
        raw_xp=raw_xp,
        base_shard=award.shard.base,
        bonus_shard=award.shard.bonus,
        power=award.power,
        status="awarded",
        calculation_version=state.calculation_version,
        calculation_inputs={
            "adjustment": str(request.adjustment),
            "grant_seq": request.grant_seq,
            "pending_shard_before": str(limits.pending_shard),
            "pending_power_before": str(limits.pending_power),
            "shard_limit": str(limits.shard_limit),
            "power_limit": str(limits.power_limit),
            "segments": [
                {
                    "start": p.start.isoformat(),
                    "end": p.end.isoformat(),
                    "channel_id": p.channel_id,
                    "rate_percent": str(p.rate_percent),
                    "shard_eligible": p.shard_eligible,
                    "power_eligible": p.power_eligible,
                }
                for p in unit.segments
            ],
        },
    )
    session.add(event)
    await session.flush()
    session.add_all(
        EventChannel(
            event_id=event.event_id,
            channel_id=channel,
            duration_us=sum(p.duration for p in unit.segments if p.channel_id == channel and p.power_eligible),
            allocated_power=power,
        )
        for channel, power in award.channel_power
    )
    session.add_all(
        EventPeriod(
            event_id=event.event_id,
            period_id=p.period_id,
            accepted=p.status == "OPEN",
            reason="open" if p.status == "OPEN" else "finalized",
            accepted_power=award.power if p.status == "OPEN" else 0,
        )
        for p in periods
    )
    session.add(
        VoiceGrant(
            user_id=request.user_id,
            grant_seq=request.grant_seq,
            measurement_epoch=request.measurement_epoch,
            operation_key=request.operation_key,
            period_end=unit.settled_at,
            committed_at=request.recorded_at,
        )
    )
    if month.status == "FINALIZED":
        await claim_locked(
            session,
            ClaimRequest(
                f"claim:{request.operation_key}",
                request.user_id,
                "late_closed_month",
                request.recorded_at,
                month.period_id,
            ),
            account,
            state,
            pending,
        )
    await session.flush()
    return await event_result(session, event)
