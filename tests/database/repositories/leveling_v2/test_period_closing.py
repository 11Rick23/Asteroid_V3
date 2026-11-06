from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import Claim, PeriodRow, RankingRow, VoicePending
from app.database.repositories.leveling_v2 import LevelingRepository, MessageAward, MutationGate
from app.database.repositories.leveling_v2.snapshots import verify_revision
from app.features.leveling.domain.periods import PeriodKind, period_at

NOW = datetime(2026, 10, 15, tzinfo=UTC)


@pytest.mark.asyncio
async def test_finalize_race(sessions: async_sessionmaker[AsyncSession]) -> None:
    """同時加算は確定前に一度含まれるか、その期間だけ不受理になる。"""
    # 非機能要件：確定順位と受理結果を分裂させず、後日の加算で確定版を書換えない。
    # Given
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    other = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    day = period_at(NOW, PeriodKind.DAY)
    barrier = asyncio.Barrier(2)

    async def award():
        await barrier.wait()
        return await repo.award_message(MessageAward(1, 1, "text", NOW, day.end, 10))

    async def close():
        await barrier.wait()
        return await other.close_period(day, day.end)

    # When
    event, revision = await asyncio.gather(award(), close())
    # Then
    async with sessions() as session:
        rows = list(
            await session.scalars(
                select(RankingRow).where(
                    RankingRow.period_id == revision.period_id,
                    RankingRow.metric == "total",
                )
            )
        )
        included = revision.period_id in event.accepted_period_ids
        assert [row.score for row in rows] == ([10] if included else [])
        assert await verify_revision(session, revision.period_id, 1) == revision
    late = await repo.award_message(MessageAward(2, 1, "text", NOW, day.end + timedelta(seconds=1), 20))
    assert revision.period_id in late.rejected_period_ids
    assert await other.close_period(day, day.end + timedelta(days=1)) == revision
    async with sessions() as session:
        assert await verify_revision(session, revision.period_id, 1) == revision


@pytest.mark.asyncio
async def test_month_claim_and_snapshot(sessions: async_sessionmaker[AsyncSession]) -> None:
    """月末全員受取とsnapshot公開は同じcommitで確定する。"""
    # 機能要件：月末未受取を恒常へ移し、既計上のpowerを順位へ一度だけ反映する。
    # Given
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    month = period_at(NOW, PeriodKind.MONTH)
    for user in (1, 2):
        await repo.award_message(MessageAward(user, user, "text", NOW, NOW, 10))
    async with sessions() as session:
        row = (await session.scalars(select(PeriodRow).where(PeriodRow.kind == "month"))).one()
        for user in (1, 2):
            session.add(
                VoicePending(
                    user_id=user,
                    month_period_id=row.period_id,
                    origin="native",
                    voice_shard=30,
                    bonus_shard=5,
                    power_meter=30,
                )
            )
        await session.commit()
    # When
    revision = await repo.close_period(month, month.end)
    # Then
    for user in (1, 2):
        account = await repo.get_account(user)
        assert account is not None and account.growth.total == 45
    async with sessions() as session:
        claims = list(await session.scalars(select(Claim)))
        assert len(claims) == 2 and all(row.shard_amount == 30 for row in claims)
        ranks = list(
            await session.scalars(
                select(RankingRow)
                .where(
                    RankingRow.period_id == revision.period_id,
                    RankingRow.metric == "total",
                )
                .order_by(RankingRow.subject_id)
            )
        )
        assert [(row.subject_id, row.score, row.rank) for row in ranks] == [(1, 10, 1), (2, 10, 1)]


@pytest.mark.asyncio
async def test_early_close_rejected(sessions: async_sessionmaker[AsyncSession]) -> None:
    """期間終了前の確定要求は期間行も公開版も作らない。"""
    # 非機能要件：DR07により期限前の強制確定を許さない。
    # Given
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    # When / Then
    with pytest.raises(ValueError, match="期間終了前"):
        await repo.close_period(period_at(NOW, PeriodKind.DAY), NOW)
    async with sessions() as session:
        assert list(await session.scalars(select(PeriodRow))) == []


@pytest.mark.asyncio
async def test_month_close_replay(sessions: async_sessionmaker[AsyncSession]) -> None:
    """同時の月末再実行でも公開版は一つで、両呼出しが同じ結果を返す。"""
    # 非機能要件：periodロック待機後に古いread snapshotを使わない。
    # Given
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    other = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    month = period_at(NOW, PeriodKind.MONTH)
    await repo.award_message(MessageAward(1, 1, "text", NOW, NOW, 10))
    barrier = asyncio.Barrier(2)

    async def run(target: LevelingRepository):
        await barrier.wait()
        return await target.close_period(month, month.end)

    # When
    first, second = await asyncio.gather(run(repo), run(other))
    # Then
    assert first == second and first.revision == 1
