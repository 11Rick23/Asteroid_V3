from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.repositories.leveling_v2.audit import record_operation, request_digest
from app.database.repositories.leveling_v2.history_queries import HistoryRepository
from app.database.repositories.leveling_v2.locks import MutationGate
from app.database.repositories.leveling_v2.outbox import OutboxRepository, enqueue
from app.database.repositories.leveling_v2.retention import RetentionRepository
from app.database.repositories.leveling_v2.transaction import VersionConflict

NOW = datetime(2026, 11, 1, tzinfo=UTC)


@pytest.mark.asyncio
async def test_single_lease(sessions: async_sessionmaker[AsyncSession]) -> None:
    """同じジョブを複数workerが同時に取得してもlease所有者は一つになる。"""
    # 非機能要件：重複キーでpayloadを書換えず、配送所有権をDBで排他する。
    # Given
    async with sessions() as session:
        first = await enqueue(session, dedupe_key="job:1", job_type="announcement", payload={"part": 1}, now=NOW)
        same = await enqueue(session, dedupe_key="job:1", job_type="announcement", payload={"part": 1}, now=NOW)
        await session.commit()
    assert first == same
    repo = OutboxRepository(sessions)
    # When
    results = await asyncio.gather(*(repo.lease(NOW) for _ in range(4)))
    # Then
    leased = [row for row in results if row is not None]
    assert len(leased) == 1
    job = leased[0]
    assert job.lease_token is not None
    with pytest.raises(VersionConflict):
        await repo.finish(job.job_id, "stale", state="completed", now=NOW)
    complete = await repo.finish(job.job_id, job.lease_token, state="completed", now=NOW)
    assert complete.state == "completed"
    assert await repo.finish(job.job_id, job.lease_token, state="completed", now=NOW) == complete
    assert await repo.lease(NOW) is None


@pytest.mark.asyncio
async def test_expired_is_unknown(sessions: async_sessionmaker[AsyncSession]) -> None:
    """leaseの期限切れは送信未完了と断定せず、自動再送を止める。"""
    # 非機能要件：送信結果不明時の重複POSTを防ぐ永続状態を保持する。
    # Given
    async with sessions() as session:
        await enqueue(session, dedupe_key="job:1", job_type="announcement", payload={}, now=NOW)
        await session.commit()
    repo = OutboxRepository(sessions)
    await repo.lease(NOW)
    # When
    count = await repo.recover_expired(NOW + timedelta(minutes=6))
    # Then
    assert count == 1
    assert await repo.lease(NOW + timedelta(days=1)) is None
    job = await repo.get("job:1")
    assert job is not None and job.state == "unknown"


@pytest.mark.asyncio
async def test_payload_conflict(sessions: async_sessionmaker[AsyncSession]) -> None:
    """同じキーの別要求を拒否し、最初のpayloadを保存する。"""
    # 非機能要件：冪等キーの再利用で送信内容をすり替えない。
    # Given
    async with sessions() as session:
        await enqueue(session, dedupe_key="job:1", job_type="announcement", payload={"part": 1}, now=NOW)
        await session.commit()
    # When
    async with sessions() as session:
        with pytest.raises(ValueError, match="別の要求"):
            await enqueue(session, dedupe_key="job:1", job_type="announcement", payload={"part": 2}, now=NOW)
        await session.rollback()
    # Then
    job = await OutboxRepository(sessions).get("job:1")
    assert job is not None and job.payload == {"part": 1}


@pytest.mark.asyncio
async def test_audit_survives_job_expiry(sessions: async_sessionmaker[AsyncSession]) -> None:
    """完了jobを90日後に回収しても永久操作台帳に実行結果を残す。"""
    # 非機能要件：完了と監査転記を同時commitし、未完了jobは回収しない。
    # Given
    async with sessions() as session:
        await record_operation(
            session,
            key="audit:1",
            kind="test_approval",
            actor_id=99,
            digest=request_digest({}),
            before={},
            after={},
            now=NOW,
        )
        await enqueue(
            session, dedupe_key="job:done", job_type="announcement", payload={}, now=NOW, audit_operation_key="audit:1"
        )
        await enqueue(session, dedupe_key="job:pending", job_type="announcement", payload={}, now=NOW)
        await session.commit()
    repo = OutboxRepository(sessions)
    job = await repo.lease(NOW)
    assert job is not None and job.lease_token is not None
    # When
    await repo.finish(job.job_id, job.lease_token, state="completed", now=NOW, audit_result="sent")
    purged = await RetentionRepository(sessions, MutationGate()).purge(NOW + timedelta(days=90))
    # Then
    assert purged.jobs == 1
    assert await repo.get("job:done") is None
    assert await repo.get("job:pending") is not None
    operation = await HistoryRepository(sessions).operation("audit:1")
    assert operation is not None
    results = operation.after["outbox_results"]
    assert isinstance(results, dict) and results["job:done"]["result"] == "sent"
