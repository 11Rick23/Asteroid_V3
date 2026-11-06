from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import Event, MessageReceipt, PeriodUser, VoicePending
from app.database.repositories.leveling_v2 import ClaimRequest, LevelingRepository, MessageAward, MutationGate
from app.database.repositories.leveling_v2.retention import RetentionRepository
from app.database.repositories.leveling_v2.snapshots import verify_revision
from app.features.leveling.domain.periods import PeriodKind, period_at

NOW = datetime(2026, 10, 15, tzinfo=UTC)


@pytest.mark.asyncio
async def test_expiry_keeps_permanent(sessions: async_sessionmaker[AsyncSession]) -> None:
    """90日履歴の削除後も恒常・受取結果・確定版を再確認できる。"""
    # 非機能要件：履歴削除を永久残高と監査台帳へ波及させない。
    # Given
    gate = MutationGate()
    repo = LevelingRepository(sessions, gate=gate, coverage_start_at=NOW)
    cleanup = RetentionRepository(sessions, gate)
    day = period_at(NOW, PeriodKind.DAY)
    await repo.award_message(MessageAward(1, 1, "text", NOW, NOW, 10))
    claim_request = ClaimRequest("manual", 1, "manual", NOW)
    claim = await repo.claim(claim_request)
    revision = await repo.close_period(day, day.end)
    # When
    before = await cleanup.purge(NOW + timedelta(days=90, microseconds=-1))
    expired = await cleanup.purge(NOW + timedelta(days=90))
    # Then
    assert before.events == before.receipts == 0
    assert expired.events == expired.receipts == 1
    assert await repo.claim(claim_request) == claim
    assert (await repo.get_account(1)) is not None
    async with sessions() as session:
        assert list(await session.scalars(select(Event))) == []
        assert list(await session.scalars(select(MessageReceipt))) == []
        assert await verify_revision(session, revision.period_id, 1) == revision
    # 作業表だけを1行batchで回収しても公開版は不変。
    assert await cleanup.reclaim_open(revision.period_id, limit=1) == 1
    assert await cleanup.reclaim_open(revision.period_id, limit=1) == 0
    async with sessions() as session:
        assert await verify_revision(session, revision.period_id, 1) == revision
        assert len(list(await session.scalars(select(PeriodUser)))) == 2


@pytest.mark.asyncio
async def test_late_event_retention(sessions: async_sessionmaker[AsyncSession]) -> None:
    """獲得時刻が古くても記録時から90日はイベントを保持する。"""
    # 機能要件：未受取残高も日時による回収対象にしない。
    # Given
    gate = MutationGate()
    repo = LevelingRepository(sessions, gate=gate, coverage_start_at=NOW)
    recorded = NOW + timedelta(days=120)
    event = await repo.award_message(MessageAward(1, 1, "text", NOW, recorded, 10))
    async with sessions() as session:
        session.add(
            VoicePending(
                user_id=1,
                month_period_id=event.accepted_period_ids[0],
                origin="legacy",
                voice_shard=500,
                bonus_shard=0,
                power_meter=500,
            )
        )
        await session.commit()
    # When
    result = await RetentionRepository(sessions, gate).purge(recorded + timedelta(days=89))
    # Then
    assert result.events == result.receipts == 0
    async with sessions() as session:
        pending = (await session.scalars(select(VoicePending))).one()
        assert pending.voice_shard == 500
        assert await session.get(Event, event.event_id) is not None
