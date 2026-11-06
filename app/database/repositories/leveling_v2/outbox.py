"""配送を行わない永続ジョブ基盤。外部処理の成否不明を自動再送しない。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import OutboxJob
from app.features.leveling.domain.numbers import identifier
from app.features.leveling.domain.periods import aware

from .dto import OutboxData
from .outbox_audit import completed_result, lock_audit, record_completion
from .storage import ensure
from .transaction import Resolution, Transactions, VersionConflict


def job_data(row: OutboxJob) -> OutboxData:
    return OutboxData(
        row.job_id, row.dedupe_key, row.type, deepcopy(row.payload), row.state, row.attempt_count, row.lease_token
    )


async def enqueue(
    session: AsyncSession,
    *,
    dedupe_key: str,
    job_type: str,
    payload: dict[str, object],
    now: datetime,
    audit_operation_key: str | None = None,
) -> OutboxData:
    """数量writerのtx末尾からも使用する。ここではcommitしない。"""
    aware(now)
    if not dedupe_key or len(dedupe_key) > 191 or not job_type or len(job_type) > 32:
        raise ValueError("ジョブ識別子が不正です")
    await ensure(
        session,
        OutboxJob,
        {
            "dedupe_key": dedupe_key,
            "type": job_type,
            "payload": deepcopy(payload),
            "state": "pending",
            "next_attempt_at": now,
            "audit_operation_key": audit_operation_key,
        },
        "job_id",
    )
    row = (await session.scalars(select(OutboxJob).where(OutboxJob.dedupe_key == dedupe_key).with_for_update())).one()
    if row.type != job_type or row.payload != payload or row.audit_operation_key != audit_operation_key:
        raise ValueError("ジョブキーが別の要求に使用されています")
    return job_data(row)


class OutboxRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions
        self.transactions = Transactions(sessions)

    async def get(self, dedupe_key: str) -> OutboxData | None:
        async with self.sessions() as session:
            row = (await session.scalars(select(OutboxJob).where(OutboxJob.dedupe_key == dedupe_key))).one_or_none()
            return None if row is None else job_data(row)

    async def lease(self, now: datetime, *, duration: timedelta = timedelta(minutes=5)) -> OutboxData | None:
        aware(now)
        if duration <= timedelta(0):
            raise ValueError("lease期間は正で指定してください")
        token = uuid4().hex

        async def action(session: AsyncSession) -> OutboxData | None:
            row = (
                await session.scalars(
                    select(OutboxJob)
                    .where(OutboxJob.state.in_(("pending", "retry_wait")), OutboxJob.next_attempt_at <= now)
                    .order_by(OutboxJob.next_attempt_at, OutboxJob.job_id)
                    .limit(1)
                    .with_for_update(skip_locked=True)
                )
            ).one_or_none()
            if row is None:
                return None
            row.state = "leased"
            row.lease_token = token
            row.lease_until = now + duration
            row.attempt_count += 1
            return job_data(row)

        async def resolve(session: AsyncSession) -> Resolution[OutboxData | None]:
            row = (await session.scalars(select(OutboxJob).where(OutboxJob.lease_token == token))).one_or_none()
            return Resolution(row is not None, None if row is None else job_data(row))

        return await self.transactions.run(action, resolve)

    async def finish(
        self,
        job_id: int,
        token: str,
        *,
        state: str,
        now: datetime,
        next_attempt_at: datetime | None = None,
        error_code: str | None = None,
        audit_result: str = "completed",
    ) -> OutboxData:
        identifier(job_id)
        aware(now)
        if not audit_result or len(audit_result) > 32:
            raise ValueError("監査結果の分類が不正です")
        if state not in ("completed", "retry_wait", "unknown", "needs_attention"):
            raise ValueError("ジョブ終了状態が不正です")
        if error_code is not None and (not error_code or len(error_code) > 64):
            raise ValueError("エラー分類が不正です")
        if state == "retry_wait":
            if next_attempt_at is None or aware(next_attempt_at) < aware(now):
                raise ValueError("再試行予定時刻が不正です")

        def matches(row: OutboxJob) -> bool:
            return (
                row.lease_token == token
                and row.state == state
                and row.last_error_code == error_code
                and (state != "retry_wait" or row.next_attempt_at == next_attempt_at)
            )

        async def action(session: AsyncSession) -> OutboxData:
            operation, choice = await lock_audit(session, job_id)
            row = (
                await session.scalars(
                    select(OutboxJob)
                    .where(OutboxJob.job_id == job_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).one_or_none()
            if row is None or row.lease_token != token:
                raise VersionConflict("古いleaseでは完了できません")
            if row.state != "leased":
                if matches(row):
                    recorded = completed_result(operation, row)
                    if (
                        state == "completed"
                        and operation is not None
                        and (not isinstance(recorded, dict) or recorded.get("result") != audit_result)
                    ):
                        raise VersionConflict("記録済み監査結果と一致しません")
                    return job_data(row)
                raise VersionConflict("ジョブ状態は既に変更されています")
            row.state = state
            row.last_error_code = error_code
            row.lease_until = None
            if next_attempt_at is not None:
                row.next_attempt_at = next_attempt_at
            if state == "completed":
                row.completed_at = now
                record_completion(operation, choice, row, now, audit_result)
                row.expires_at = now + timedelta(days=90)
            return job_data(row)

        async def resolve(session: AsyncSession) -> Resolution[OutboxData]:
            row = await session.get(OutboxJob, job_id)
            return Resolution(row is not None and matches(row), None if row is None else job_data(row))

        return await self.transactions.run(action, resolve)

    async def recover_expired(self, now: datetime, *, limit: int = 100) -> int:
        """再起動後のlease切れはUNKNOWNへ。期限だけを根拠に再送しない。"""
        aware(now)
        if not 1 <= limit <= 1000:
            raise ValueError("batch件数が不正です")
        async with self.sessions() as session:
            rows = list(
                await session.scalars(
                    select(OutboxJob)
                    .where(OutboxJob.state == "leased", OutboxJob.lease_until <= now)
                    .order_by(OutboxJob.job_id)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            for row in rows:
                row.state = "unknown"
                row.lease_until = None
                row.last_error_code = "lease_expired"
            await session.commit()
            return len(rows)
