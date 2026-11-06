"""P2専用Repository。既存DatabaseRepositoriesには接続しない。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import Account, PeriodRow, VoiceState
from app.features.leveling.domain.numbers import identifier
from app.features.leveling.domain.periods import Period, aware

from .claims import ClaimRequest, claim_locked, find_claim
from .closing import close_period, find_closed
from .corrections import SnapshotCorrection, correct_snapshot, find_correction
from .dto import AccountData, AwardResult, ClaimResult, RevisionResult, VoiceStateData
from .locks import MutationGate
from .messages import MessageAward, apply_message, find_message
from .storage import account_data, lock_accounts, lock_pending, lock_states
from .transaction import DuplicateOperation, Transactions
from .voice_request import VoiceSettlement
from .voice_settlement import find_grant, settle_voice
from .voice_state import Checkpoint, resolve_checkpoint, save_checkpoint, state_data


class LevelingRepository:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        gate: MutationGate,
        coverage_start_at: datetime,
    ) -> None:
        """同一DBの全writerに同じgateを明示注入する。接続設定は読み込まない。"""
        aware(coverage_start_at)
        self.sessions = sessions
        self.gate = gate
        self.coverage_start_at = coverage_start_at
        self.transactions = Transactions(sessions)

    async def get_account(self, user_id: int) -> AccountData | None:
        identifier(user_id)
        async with self.sessions() as session:
            row = await session.get(Account, user_id)
            return None if row is None else account_data(row)

    async def award_message(self, request: MessageAward) -> AwardResult:
        async with self.gate.shared(request.user_id):
            return await self.transactions.run(
                lambda session: apply_message(session, request, self.coverage_start_at),
                lambda session: find_message(session, request.message_id, request.recorded_at),
            )

    async def claim(self, request: ClaimRequest) -> ClaimResult:
        async with self.gate.shared(request.user_id):
            return await self.transactions.run(
                lambda session: self._claim(session, request),
                lambda session: find_claim(session, request),
            )

    async def get_voice_state(self, user_id: int) -> VoiceStateData | None:
        identifier(user_id)
        async with self.sessions() as session:
            row = await session.get(VoiceState, user_id)
            return None if row is None else await state_data(session, row)

    async def checkpoint(self, request: Checkpoint) -> VoiceStateData:
        async with self.gate.shared(request.user_id, coordinator=True):
            return await self.transactions.run(
                lambda session: save_checkpoint(session, request),
                lambda session: resolve_checkpoint(session, request),
            )

    async def settle_voice(self, request: VoiceSettlement) -> AwardResult:
        async with self.gate.shared(request.user_id, coordinator=True):
            return await self.transactions.run(
                lambda session: settle_voice(session, request, self.coverage_start_at),
                lambda session: find_grant(session, request),
            )

    async def close_period(self, period: Period, now: datetime) -> RevisionResult:
        async with self.gate.exclusive():
            return await self.transactions.run(
                lambda session: close_period(session, period, now, self.coverage_start_at),
                lambda session: find_closed(session, period),
            )

    async def correct_snapshot(self, request: SnapshotCorrection) -> RevisionResult:
        async with self.gate.exclusive():
            return await self.transactions.run(
                lambda session: correct_snapshot(session, request),
                lambda session: find_correction(session, request),
            )

    async def _claim(self, session: AsyncSession, request: ClaimRequest) -> ClaimResult:
        if (await find_claim(session, request)).found:
            raise DuplicateOperation()
        if request.month_period_id is not None:
            period = (
                await session.scalars(
                    select(PeriodRow).where(PeriodRow.period_id == request.month_period_id).with_for_update()
                )
            ).one_or_none()
            if period is None or period.kind != "month":
                raise ValueError("受取対象月が存在しません")
            if period.end_at > request.committed_at:
                raise ValueError("月終了前の自動受取はできません")
            if request.trigger == "late_closed_month" and period.status != "FINALIZED":
                raise ValueError("遅延受取には確定済み月を指定してください")
        account = (await lock_accounts(session, (request.user_id,)))[0]
        states = await lock_states(session, (request.user_id,))
        pending = await lock_pending(session, (request.user_id,))
        return await claim_locked(session, request, account, states[0] if states else None, pending)
