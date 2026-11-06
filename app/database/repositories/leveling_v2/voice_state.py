"""既知区間保存専用CAS。付与へ昇格せず、未精算区間は期限削除しない。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.leveling_v2 import VoiceSegmentRow, VoiceState
from app.features.leveling.domain.numbers import amount, identifier, integer
from app.features.leveling.domain.periods import aware
from app.features.leveling.domain.voice_time import VoiceSegment, validate_segments

from .dto import VoiceStateData
from .storage import lock_accounts, lock_states
from .transaction import Resolution, VersionConflict


@dataclass(frozen=True)
class Checkpoint:
    user_id: int
    expected_version: int | None
    expected_epoch: str | None
    measurement_epoch: str
    state: str
    confirmed_at: datetime
    channel_id: int | None
    segments: tuple[VoiceSegment, ...] = ()
    prepared_random: int | None = None
    calculation_version: str = "p1"

    def __post_init__(self) -> None:
        identifier(self.user_id)
        aware(self.confirmed_at)
        if self.channel_id is not None:
            identifier(self.channel_id)
        if self.expected_version is not None:
            integer(self.expected_version, maximum=2**64 - 2)
        if (self.expected_version is None) != (self.expected_epoch is None):
            raise ValueError("既存状態のversionとepochを組で指定してください")
        if not self.measurement_epoch or len(self.measurement_epoch) > 64:
            raise ValueError("計測epochが不正です")
        if not self.calculation_version or len(self.calculation_version) > 64:
            raise ValueError("計算バージョンが不正です")
        if self.state not in ("tracking", "suspended", "reconciling", "stopped"):
            raise ValueError("計測状態が不正です")
        validate_segments(self.segments)
        if any(part.end > self.confirmed_at for part in self.segments):
            raise ValueError("確認時刻より未来の区間は保存できません")
        if any(not (part.shard_eligible or part.power_eligible) for part in self.segments):
            raise ValueError("両側停止区間を保存できません")
        if self.prepared_random is not None:
            amount(self.prepared_random)


async def segment_rows(session: AsyncSession, user_id: int, *, lock: bool = False) -> list[VoiceSegmentRow]:
    query = select(VoiceSegmentRow).where(VoiceSegmentRow.user_id == user_id).order_by(VoiceSegmentRow.segment_seq)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return list(await session.scalars(query))


def segment_data(row: VoiceSegmentRow) -> VoiceSegment:
    rate = int(row.rate_snapshot)
    if str(rate) != row.rate_snapshot:
        raise ValueError("率snapshotは正規化整数文字列である必要があります")
    result = VoiceSegment(row.start_at, row.end_at, row.channel_id, rate, row.shard_eligible, row.power_eligible)
    if result.duration != row.duration_us:
        raise ValueError("保存済みVC区間の時間が一致しません")
    return result


async def state_data(session: AsyncSession, row: VoiceState) -> VoiceStateData:
    parts = tuple(segment_data(part) for part in await segment_rows(session, row.user_id))
    validate_segments(parts)
    return VoiceStateData(
        row.user_id,
        row.measurement_epoch,
        row.state,
        row.last_channel_id,
        row.last_confirmed_at,
        row.checkpoint_version,
        row.next_grant_seq,
        row.prepared_grant_seq,
        row.prepared_random,
        row.calculation_version,
        row.consumed_segment_seq,
        row.consumed_offset_us,
        row.eligible_elapsed_us,
        row.pending_cycle,
        row.cap_notice_attempted,
        parts,
    )


async def resolve_checkpoint(session: AsyncSession, request: Checkpoint) -> Resolution[VoiceStateData]:
    row = await session.get(VoiceState, request.user_id)
    version = 0 if request.expected_version is None else request.expected_version + 1
    if (
        row is None
        or row.checkpoint_version != version
        or row.measurement_epoch != request.measurement_epoch
        or row.last_confirmed_at != request.confirmed_at
        or row.last_channel_id != request.channel_id
        or row.state != request.state
        or row.calculation_version != request.calculation_version
    ):
        return Resolution(False)
    result = await state_data(session, row)
    if request.segments and result.segments[-len(request.segments) :] != request.segments:
        return Resolution(False)
    if request.prepared_random is not None and row.prepared_random != request.prepared_random:
        return Resolution(False)
    return Resolution(True, result)


async def save_checkpoint(session: AsyncSession, request: Checkpoint) -> VoiceStateData:
    await lock_accounts(session, (request.user_id,))
    states = await lock_states(session, (request.user_id,))
    row = states[0] if states else None
    if row is None:
        if request.expected_version is not None:
            raise VersionConflict("計測状態が存在しません")
        row = VoiceState(
            user_id=request.user_id,
            measurement_epoch=request.measurement_epoch,
            state=request.state,
            last_channel_id=request.channel_id,
            last_confirmed_at=request.confirmed_at,
            calculation_version=request.calculation_version,
        )
        session.add(row)
        await session.flush()
    else:
        if row.checkpoint_version != request.expected_version or row.measurement_epoch != request.expected_epoch:
            raise VersionConflict("checkpointのversionまたはepochが一致しません")
        if request.confirmed_at < row.last_confirmed_at:
            raise ValueError("確認時刻を巻き戻せません")
        if request.segments and request.segments[0].start < row.last_confirmed_at:
            raise ValueError("確認済み時間を再投入できません")
        if row.prepared_random is not None and request.calculation_version != row.calculation_version:
            raise ValueError("未精算単位の計算バージョンは変更できません")
        row.checkpoint_version += 1
    rows = await segment_rows(session, request.user_id, lock=True)
    if rows and request.segments and rows[-1].end_at > request.segments[0].start:
        raise ValueError("保存区間が重複しています")
    if request.segments and row.prepared_random is None:
        if request.prepared_random is None:
            raise ValueError("最初の区間保存には固定乱数が必要です")
        row.prepared_random = request.prepared_random
        row.prepared_grant_seq = row.next_grant_seq
    elif request.prepared_random is not None and request.prepared_random != row.prepared_random:
        raise ValueError("保存済み乱数の変更はできません")
    seq = max(row.consumed_segment_seq, rows[-1].segment_seq if rows else 0)
    for part in request.segments:
        seq = identifier(seq + 1)
        session.add(
            VoiceSegmentRow(
                user_id=request.user_id,
                segment_seq=seq,
                start_at=part.start,
                end_at=part.end,
                channel_id=part.channel_id,
                duration_us=part.duration,
                rate_snapshot=str(part.rate_percent),
                shard_eligible=part.shard_eligible,
                power_eligible=part.power_eligible,
                grant_seq=row.next_grant_seq,
            )
        )
    row.measurement_epoch = request.measurement_epoch
    row.state = request.state
    row.last_confirmed_at = request.confirmed_at
    row.last_channel_id = request.channel_id
    row.calculation_version = request.calculation_version
    row.eligible_elapsed_us = sum(part.duration_us for part in rows) + sum(part.duration for part in request.segments)
    integer(row.eligible_elapsed_us, maximum=2**63 - 1)
    await session.flush()
    return await state_data(session, row)
