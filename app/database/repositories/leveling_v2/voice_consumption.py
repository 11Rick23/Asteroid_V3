"""付与tx内の区間消費。消費カーソルは履歴削除後も巻き戻さない。"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.leveling_v2 import VoiceSegmentRow, VoiceState
from app.features.leveling.domain.numbers import identifier
from app.features.leveling.domain.voice_time import VoiceStep


async def consume(
    session: AsyncSession,
    state: VoiceState,
    rows: list[VoiceSegmentRow],
    step: VoiceStep,
    next_random: int | None,
) -> None:
    if step.unit is None:
        raise ValueError("消費対象の付与単位がありません")
    if step.remaining and next_random is None:
        raise ValueError("残余の次単位を準備する固定乱数が必要です")
    left = step.unit.duration
    for row in rows:
        if not left:
            break
        consumed = min(left, row.duration_us)
        offset = state.consumed_offset_us if state.consumed_segment_seq == row.segment_seq else 0
        state.consumed_segment_seq = row.segment_seq
        state.consumed_offset_us = offset + consumed
        if consumed == row.duration_us:
            await session.delete(row)
        else:
            row.start_at += timedelta(microseconds=consumed)
            row.duration_us -= consumed
        left -= consumed
    if left:
        raise ValueError("保存区間と消費単位が一致しません")
    state.next_grant_seq = identifier(state.next_grant_seq + 1)
    state.checkpoint_version = identifier(state.checkpoint_version + 1)
    state.prepared_grant_seq = state.next_grant_seq if step.remaining else None
    state.prepared_random = next_random if step.remaining else None
    state.eligible_elapsed_us = sum(part.duration for part in step.remaining)
    for row in rows:
        if row not in session.deleted:
            row.grant_seq = state.next_grant_seq
