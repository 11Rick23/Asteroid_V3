from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import CorrectionChange, Operation, PeriodRow, RankingRow
from app.database.repositories.leveling_v2 import LevelingRepository, MessageAward, MutationGate
from app.database.repositories.leveling_v2.corrections import SnapshotCorrection
from app.database.repositories.leveling_v2.snapshots import SnapshotInputs, verify_revision
from app.database.repositories.leveling_v2.transaction import VersionConflict
from app.features.leveling.domain.periods import PeriodKind, period_at

NOW = datetime(2026, 10, 15, tzinfo=UTC)


@pytest.mark.asyncio
async def test_revision_history(sessions: async_sessionmaker[AsyncSession]) -> None:
    """訂正は新revisionへ公開し、旧順位と間接的な順位変更の監査を残す。"""
    # 機能要件：初回版は不変で、訂正結果は冪等キーで再確認できる。
    # Given
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    day = period_at(NOW, PeriodKind.DAY)
    await repo.award_message(MessageAward(1, 1, "text", NOW, NOW, 20))
    await repo.award_message(MessageAward(2, 2, "text", NOW, NOW, 10))
    original = await repo.close_period(day, day.end)
    proposal = SnapshotCorrection(
        "request-1",
        original.period_id,
        1,
        99,
        "誤計上の訂正",
        day.end,
        day.end,
        "",
        SnapshotInputs({1: (5, 0, 0), 2: (10, 0, 0)}, {}),
    )
    approved = replace(proposal, preview_hash=proposal.digest())
    # When
    corrected = await repo.correct_snapshot(approved)
    # Then
    assert corrected.revision == 2 and corrected.checksum != original.checksum
    assert await repo.correct_snapshot(approved) == corrected
    async with sessions() as session:
        assert await verify_revision(session, original.period_id, 1) == original
        changes = list(await session.scalars(select(CorrectionChange).where(CorrectionChange.metric == "total")))
        by_user = {row.subject_id: row for row in changes}
        assert (by_user[1].old_score, by_user[1].new_score) == (20, 5)
        assert (by_user[2].old_rank, by_user[2].new_rank) == (2, 1)
        period = await session.get(PeriodRow, original.period_id)
        assert period is not None and period.current_revision == 2
        assert (await session.scalars(select(Operation))).one().status == "completed"
        ranks = list(
            await session.scalars(
                select(RankingRow)
                .where(
                    RankingRow.period_id == original.period_id,
                    RankingRow.revision == 2,
                    RankingRow.metric == "total",
                )
                .order_by(RankingRow.rank)
            )
        )
        assert [(row.subject_id, row.score) for row in ranks] == [(2, 10), (1, 5)]
    stale = replace(approved, request_key="request-2", preview_hash="")
    with pytest.raises(VersionConflict):
        await repo.correct_snapshot(replace(stale, preview_hash=stale.digest()))


@pytest.mark.asyncio
async def test_approval_mismatch(sessions: async_sessionmaker[AsyncSession]) -> None:
    """承認後に入力が変わっていれば台帳・新revisionを保存しない。"""
    # 非機能要件：承認hashと実際の公開内容の一致を確認する。
    # Given
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    day = period_at(NOW, PeriodKind.DAY)
    original = await repo.close_period(day, day.end)
    proposal = SnapshotCorrection(
        "request", original.period_id, 1, 99, "訂正", day.end, day.end, "incorrect", SnapshotInputs({}, {})
    )
    # When / Then
    with pytest.raises(ValueError, match="preview hash"):
        await repo.correct_snapshot(proposal)
    async with sessions() as session:
        assert list(await session.scalars(select(Operation))) == []
        assert await verify_revision(session, original.period_id, 1) == original


@pytest.mark.asyncio
async def test_same_request_concurrently(sessions: async_sessionmaker[AsyncSession]) -> None:
    """同じ承認操作を別セッションで再送しても訂正版を一つだけ作る。"""
    # 非機能要件：version待機後は永久キーを新しい読取りで再確認する。
    # Given
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    other = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    day = period_at(NOW, PeriodKind.DAY)
    original = await repo.close_period(day, day.end)
    request = SnapshotCorrection(
        "same-key", original.period_id, 1, 99, "訂正", day.end, day.end, "", SnapshotInputs({1: (10, 0, 0)}, {})
    )
    approved = replace(request, preview_hash=request.digest())
    barrier = asyncio.Barrier(2)

    async def run(target: LevelingRepository):
        await barrier.wait()
        return await target.correct_snapshot(approved)

    # When
    first, second = await asyncio.gather(run(repo), run(other))
    # Then
    assert first == second and first.revision == 2
    async with sessions() as session:
        assert len(list(await session.scalars(select(Operation)))) == 1
