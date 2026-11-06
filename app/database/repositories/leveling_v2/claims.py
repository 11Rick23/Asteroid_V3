"""未受取残高の原子的な受取。期間powerは獲得時の値を維持する。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.leveling_v2 import Account, Claim, ClaimItem, VoicePending, VoiceState
from app.features.leveling.domain.numbers import identifier, total_amount
from app.features.leveling.domain.periods import aware

from .dto import ClaimResult
from .storage import add_growth
from .transaction import DuplicateOperation, Resolution


@dataclass(frozen=True)
class ClaimRequest:
    operation_key: str
    user_id: int
    trigger: str
    committed_at: datetime
    month_period_id: int | None = None

    def __post_init__(self) -> None:
        identifier(self.user_id)
        aware(self.committed_at)
        if not self.operation_key or len(self.operation_key) > 191:
            raise ValueError("受取キーが不正です")
        if self.trigger not in ("manual", "month_close", "late_closed_month"):
            raise ValueError("受取種別が不正です")
        if (self.trigger == "manual") != (self.month_period_id is None):
            raise ValueError("手動受取は全月、自動受取は指定月を対象とします")
        if self.month_period_id is not None:
            identifier(self.month_period_id)


def claim_data(row: Claim) -> ClaimResult:
    return ClaimResult(
        row.claim_id, row.operation_key, row.user_id, row.shard_amount, row.bonus_amount, row.power_released
    )


async def find_claim(session: AsyncSession, request: ClaimRequest) -> Resolution[ClaimResult]:
    row = (await session.scalars(select(Claim).where(Claim.operation_key == request.operation_key))).one_or_none()
    if row is None:
        return Resolution(False)
    if (
        row.user_id != request.user_id
        or row.trigger != request.trigger
        or row.month_period_id != request.month_period_id
    ):
        raise ValueError("受取キーが別の要求に使用されています")
    return Resolution(True, claim_data(row))


async def claim_locked(
    session: AsyncSession,
    request: ClaimRequest,
    account: Account,
    state: VoiceState | None,
    pending: list[VoicePending],
) -> ClaimResult:
    """呼出し側がperiod→account→state→pendingを全件ロックした後に呼ぶ。"""
    if account.user_id != request.user_id or (state is not None and state.user_id != request.user_id):
        raise ValueError("受取対象とロック済みユーザーが一致しません")
    if (await find_claim(session, request)).found:
        raise DuplicateOperation()
    selected = [
        row
        for row in pending
        if row.user_id == request.user_id
        and (request.month_period_id is None or row.month_period_id == request.month_period_id)
    ]
    voice = total_amount(*(row.voice_shard for row in selected))
    bonus = total_amount(*(row.bonus_shard for row in selected))
    power = total_amount(*(row.power_meter for row in selected))
    # 数量検証・成長計算はP1の関数に委譲する。例外時は外側のtx全体をrollbackする。
    add_growth(account, voice=voice, bonus=bonus)
    claim = Claim(
        operation_key=request.operation_key,
        user_id=request.user_id,
        trigger=request.trigger,
        month_period_id=request.month_period_id,
        shard_amount=voice,
        bonus_amount=bonus,
        power_released=power,
        committed_at=request.committed_at,
    )
    session.add(claim)
    await session.flush()
    for row in selected:
        session.add(
            ClaimItem(
                claim_id=claim.claim_id,
                month_period_id=row.month_period_id,
                origin=row.origin,
                before_voice_shard=row.voice_shard,
                before_bonus_shard=row.bonus_shard,
                before_power_meter=row.power_meter,
                claimed_voice_shard=row.voice_shard,
                claimed_bonus_shard=row.bonus_shard,
                claimed_power_meter=row.power_meter,
            )
        )
        row.voice_shard = row.bonus_shard = row.power_meter = 0
        row.version += 1
    if state is not None:
        state.checkpoint_version += 1
        state.pending_cycle += 1
        state.cap_notice_attempted = False
    await session.flush()
    return claim_data(claim)
