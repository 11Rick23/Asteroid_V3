from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import CorrectionRoleChoice, MonthlyQualification, PermanentAward, RoleDesire
from app.database.repositories.leveling_v2 import LevelingRepository, MessageAward, MutationGate
from app.database.repositories.leveling_v2.corrections import SnapshotCorrection
from app.database.repositories.leveling_v2.outbox import OutboxRepository
from app.database.repositories.leveling_v2.retention import RetentionRepository
from app.database.repositories.leveling_v2.role_decisions import RoleDecision
from app.database.repositories.leveling_v2.snapshots import SnapshotInputs
from app.features.leveling.domain.periods import PeriodKind, period_at


@pytest.mark.asyncio
@pytest.mark.parametrize("revoke", [False, True])
async def test_recalculate_following_months(sessions: async_sessionmaker[AsyncSession], revoke: bool) -> None:
    """過去月のTOP1取消で後続月を再判定し、過去の永久報酬は自動剥奪しない。"""
    # 機能要件：P1連続判定と永久獲得済み状態を区別して保存する。
    # Given
    start = datetime(2026, 1, 1, tzinfo=UTC)
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=start)
    revisions = []
    for month in (1, 2, 3):
        at = datetime(2026, month, 15, tzinfo=UTC)
        await repo.award_message(MessageAward(month, 1, "text", at, at, 20))
        period = period_at(at, PeriodKind.MONTH)
        revisions.append(await repo.close_period(period, period.end))
    async with sessions() as session:
        award = (await session.scalars(select(PermanentAward))).one()
        assert award.first_earned_month == revisions[2].period_id and award.desired_granted
        last = await session.get(MonthlyQualification, (revisions[2].period_id, 1))
        assert last is not None and last.consecutive_top1 == 3
    at = datetime(2026, 4, 2, tzinfo=UTC)
    proposal = SnapshotCorrection(
        "cancel-january",
        revisions[0].period_id,
        1,
        99,
        "原票訂正",
        at,
        at,
        "",
        SnapshotInputs({1: (10, 0, 0), 2: (30, 0, 0)}, {}),
        role_decisions=(RoleDecision(1, 900, True, False, True, False, "revoke"),) if revoke else (),
    )
    # When
    await repo.correct_snapshot(replace(proposal, preview_hash=proposal.digest()))
    # Then
    async with sessions() as session:
        first = await session.get(MonthlyQualification, (revisions[0].period_id, 1))
        last = await session.get(MonthlyQualification, (revisions[2].period_id, 1))
        assert first is not None and not first.is_top1 and first.ranking_revision == 2
        assert last is not None and last.consecutive_top1 == 2 and last.ranking_revision == 1
        award = (await session.scalars(select(PermanentAward))).one()
        assert award.desired_granted == (not revoke) and award.first_earned_month == revisions[2].period_id
    if revoke:
        outbox = OutboxRepository(sessions)
        for _ in range(4):
            job = await outbox.lease(at)
            assert job is not None and job.lease_token is not None
            await outbox.finish(
                job.job_id,
                job.lease_token,
                state="completed",
                now=at,
                audit_result="revoked" if job.type == "role_sync" else "test_noop",
            )
        assert await outbox.lease(at) is None
        await RetentionRepository(sessions, repo.gate).purge(at + timedelta(days=90))
        async with sessions() as session:
            choice = (await session.scalars(select(CorrectionRoleChoice))).one()
            assert choice.execution_result == "revoked" and choice.completed_at == at
            desire = (await session.scalars(select(RoleDesire))).one()
            assert not desire.desired and desire.generation == 1


@pytest.mark.asyncio
async def test_cutover_excludes_previous_months(sessions: async_sessionmaker[AsyncSession]) -> None:
    """移行月より前のTOP1を3ヶ月連続資格に含めない。"""
    # 機能要件：ランキング開始月からの履歴だけで連続数を算出する。
    # Given
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=datetime(2026, 2, 1, tzinfo=UTC))
    last_id = 0
    # When
    for month in (1, 2, 3):
        at = datetime(2026, month, 15, tzinfo=UTC)
        await repo.award_message(MessageAward(month, 1, "text", at, at, 20))
        period = period_at(at, PeriodKind.MONTH)
        last_id = (await repo.close_period(period, period.end)).period_id
    # Then
    async with sessions() as session:
        last = await session.get(MonthlyQualification, (last_id, 1))
        assert last is not None and last.consecutive_top1 == 2
        assert list(await session.scalars(select(PermanentAward))) == []
