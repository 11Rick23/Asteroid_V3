"""期限履歴と公開済み作業表だけを小batchで回収する。永久監査は対象外。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import (
    Event,
    MessageReceipt,
    OutboxJob,
    PeriodChannel,
    PeriodChannelUser,
    PeriodRow,
    PeriodUser,
    VoiceGrant,
)
from app.features.leveling.domain.periods import aware

from .locks import MutationGate
from .outbox_audit import completion_is_preserved
from .snapshots import verify_revision


@dataclass(frozen=True)
class PurgeResult:
    events: int
    receipts: int
    grants: int
    jobs: int


def validate_batch(limit: int) -> None:
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("回収batchは1..1000件で指定してください")


class RetentionRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], gate: MutationGate) -> None:
        self.sessions = sessions
        self.gate = gate

    async def purge(self, now: datetime, *, limit: int = 100) -> PurgeResult:
        aware(now)
        validate_batch(limit)
        # 各対象は独立した履歴。完了済みbatchからの再開が安全な削除だけを行う。
        async with self.gate.shared():
            async with self.sessions() as session:
                event_ids = tuple(
                    await session.scalars(
                        select(Event.event_id)
                        .where(
                            Event.expires_at <= now,
                        )
                        .order_by(Event.expires_at, Event.event_id)
                        .limit(limit)
                        .with_for_update(skip_locked=True)
                    )
                )
                if event_ids:
                    await session.execute(delete(Event).where(Event.event_id.in_(event_ids)))
                await session.commit()
            async with self.sessions() as session:
                message_ids = tuple(
                    await session.scalars(
                        select(MessageReceipt.message_id)
                        .where(
                            MessageReceipt.expires_at <= now,
                        )
                        .order_by(MessageReceipt.expires_at, MessageReceipt.message_id)
                        .limit(limit)
                        .with_for_update(skip_locked=True)
                    )
                )
                if message_ids:
                    await session.execute(delete(MessageReceipt).where(MessageReceipt.message_id.in_(message_ids)))
                await session.commit()
            async with self.sessions() as session:
                grants = list(
                    await session.execute(
                        select(VoiceGrant.user_id, VoiceGrant.grant_seq)
                        .where(
                            VoiceGrant.committed_at <= now - timedelta(days=90),
                        )
                        .order_by(VoiceGrant.committed_at, VoiceGrant.user_id, VoiceGrant.grant_seq)
                        .limit(limit)
                        .with_for_update(skip_locked=True)
                    )
                )
                if grants:
                    await session.execute(
                        delete(VoiceGrant).where(tuple_(VoiceGrant.user_id, VoiceGrant.grant_seq).in_(grants))
                    )
                await session.commit()
            async with self.sessions() as session:
                candidates = tuple(
                    await session.scalars(
                        select(OutboxJob)
                        .where(
                            OutboxJob.state == "completed",
                            OutboxJob.expires_at <= now,
                        )
                        .order_by(OutboxJob.expires_at, OutboxJob.job_id)
                        .limit(limit)
                        .with_for_update(skip_locked=True)
                    )
                )
                jobs: list[int] = []
                for job in candidates:
                    if await completion_is_preserved(session, job):
                        jobs.append(job.job_id)
                if jobs:
                    await session.execute(delete(OutboxJob).where(OutboxJob.job_id.in_(jobs)))
                await session.commit()
        return PurgeResult(len(event_ids), len(message_ids), len(grants), len(jobs))

    async def reclaim_open(self, period_id: int, *, limit: int = 100) -> int:
        """全正本・順位のchecksum確認後、公開済み期間の旧作業表だけを削除する。"""
        validate_batch(limit)
        async with self.gate.exclusive(), self.sessions() as session:
            period = (
                await session.scalars(
                    select(PeriodRow)
                    .where(
                        PeriodRow.period_id == period_id,
                    )
                    .with_for_update()
                )
            ).one_or_none()
            if period is None or period.status != "FINALIZED":
                raise ValueError("公開済み期間だけを回収できます")
            await verify_revision(session, period_id, period.current_revision)
            count = 0
            for model in (PeriodUser, PeriodChannelUser, PeriodChannel):
                keys = list(model.__table__.primary_key)
                rows = list(
                    await session.execute(
                        select(*keys)
                        .where(model.period_id == period_id)
                        .order_by(*keys)
                        .limit(limit - count)
                        .with_for_update()
                    )
                )
                if rows:
                    await session.execute(delete(model).where(tuple_(*keys).in_(rows)))
                    count += len(rows)
                if count == limit:
                    break
            await session.commit()
            return count
