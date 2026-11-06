from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import Channel, Claim, PeriodUser, RankingRevision, VoiceGrant, VoicePending
from app.database.repositories.leveling_v2 import LevelingRepository, MutationGate
from app.database.repositories.leveling_v2.retention import RetentionRepository
from app.database.repositories.leveling_v2.storage import lock_periods
from app.database.repositories.leveling_v2.voice_request import VoiceSettlement
from app.database.repositories.leveling_v2.voice_state import Checkpoint
from app.features.leveling.domain.periods import periods_at
from app.features.leveling.domain.voice_time import VoiceSegment

NOW = datetime(2026, 10, 15, tzinfo=UTC)


async def prepared(sessions: async_sessionmaker[AsyncSession], seconds: int = 60) -> LevelingRepository:
    async with sessions() as session:
        session.add(Channel(channel_id=10, last_name="VC", kind="voice", last_seen_at=NOW))
        await session.commit()
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    end = NOW + timedelta(seconds=seconds)
    await repo.checkpoint(
        Checkpoint(
            1,
            None,
            None,
            "epoch-a",
            "tracking",
            end,
            10,
            (VoiceSegment(NOW, end, 10),),
            25,
        )
    )
    return repo


@pytest.mark.asyncio
async def test_atomic_consumption(sessions: async_sessionmaker[AsyncSession]) -> None:
    """2単位の消費位置・固定乱数・残高・期間powerを一括で進める。"""
    # 機能要件：P1計算の7と9を付与し、未受取の間は恒常残高を増やさない。
    # Given
    repo = await prepared(sessions, 120)
    end = NOW + timedelta(seconds=120)
    request = VoiceSettlement(1, 0, "epoch-a", 1, end, end, next_random=30)
    # When
    first = await repo.settle_voice(request)
    state = await repo.get_voice_state(1)
    assert state is not None and state.checkpoint_version == 1
    second = await repo.settle_voice(VoiceSettlement(1, 1, "epoch-a", 2, end, end))
    # Then
    assert (first.base_shard, second.base_shard) == (7, 9)
    assert await repo.settle_voice(request) == first
    state = await repo.get_voice_state(1)
    assert state is not None and state.segments == () and state.next_grant_seq == 3
    assert state.consumed_segment_seq == 1 and state.consumed_offset_us == 120_000_000
    assert state.prepared_random is None
    account = await repo.get_account(1)
    assert account is not None and account.growth.total == 0
    async with sessions() as session:
        row = (await session.scalars(select(VoicePending))).one()
        assert (row.voice_shard, row.power_meter) == (16, 16)
        assert list(await session.scalars(select(PeriodUser.voice_power))) == [16, 16, 16]


@pytest.mark.asyncio
async def test_duplicate_grant(sessions: async_sessionmaker[AsyncSession]) -> None:
    """独立セッションが同じ付与を要求しても単位消費と残高は一度だけになる。"""
    # 非機能要件：grant seqとCASでcheckpointの二重適用を防ぐ。
    # Given
    repo = await prepared(sessions)
    other = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    end = NOW + timedelta(minutes=1)
    request = VoiceSettlement(1, 0, "epoch-a", 1, end, end)
    # When
    results = await asyncio.gather(repo.settle_voice(request), other.settle_voice(request))
    # Then
    assert results[0] == results[1]
    async with sessions() as session:
        row = (await session.scalars(select(VoicePending))).one()
        assert row.voice_shard == row.power_meter == 7


@pytest.mark.asyncio
async def test_closed_month_catchup(sessions: async_sessionmaker[AsyncSession]) -> None:
    """全期間確定済みの遅延VCでもシャードを受取りpower meterは消費しない。"""
    # 機能要件：DR06のcatch-up受取を付与と同じtxで永久台帳へ残す。
    # Given
    repo = await prepared(sessions)
    recorded = NOW + timedelta(days=40)
    async with sessions() as session:
        for period in await lock_periods(session, periods_at(NOW), NOW):
            session.add(
                RankingRevision(
                    period_id=period.period_id,
                    revision=1,
                    created_at=recorded,
                    source="close",
                    row_count=0,
                    checksum="0" * 64,
                )
            )
            period.status = "FINALIZED"
            period.current_revision = 1
            period.finalized_at = recorded
        await session.commit()
    # When
    result = await repo.settle_voice(VoiceSettlement(1, 0, "epoch-a", 1, NOW + timedelta(minutes=1), recorded))
    # Then
    assert result.base_shard == 7 and result.power == 0
    assert len(result.rejected_period_ids) == 3
    account = await repo.get_account(1)
    assert account is not None and account.voice_shard == 7
    async with sessions() as session:
        claim = (await session.scalars(select(Claim))).one()
        assert claim.trigger == "late_closed_month" and claim.shard_amount == 7
        pending = (await session.scalars(select(VoicePending))).one()
        assert pending.voice_shard == pending.power_meter == 0
        assert list(await session.scalars(select(PeriodUser))) == []


@pytest.mark.asyncio
async def test_missing_next_random_rolls_back(sessions: async_sessionmaker[AsyncSession]) -> None:
    """残余の乱数準備が不十分なら消費・pending加算を一切確定しない。"""
    # 非機能要件：途中の検証例外で付与単位が失われない。
    # Given
    repo = await prepared(sessions, 120)
    before = await repo.get_voice_state(1)
    end = NOW + timedelta(seconds=120)
    # When / Then
    with pytest.raises(ValueError, match="固定乱数"):
        await repo.settle_voice(VoiceSettlement(1, 0, "epoch-a", 1, end, end))
    assert await repo.get_voice_state(1) == before
    async with sessions() as session:
        assert list(await session.scalars(select(VoicePending))) == []


@pytest.mark.asyncio
async def test_voice_commit_response_lost(sessions: async_sessionmaker[AsyncSession]) -> None:
    """VC付与commit応答喪失時はgrant照会で結果を返し、乱数を再準備しない。"""
    # 非機能要件：seq・消費・pendingが一度だけ進む。
    # Given
    original = await prepared(sessions)

    class LostVoiceSession(AsyncSession):
        commits = 0

        async def commit(self) -> None:
            LostVoiceSession.commits += 1
            await super().commit()
            raise OperationalError("COMMIT", {}, Exception(2013, "injected response loss"))

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        sessions.kw["bind"],
        class_=LostVoiceSession,
        expire_on_commit=False,
    )
    repo = LevelingRepository(factory, gate=MutationGate(), coverage_start_at=NOW)
    end = NOW + timedelta(minutes=1)
    request = VoiceSettlement(1, 0, "epoch-a", 1, end, end)
    # When
    result = await repo.settle_voice(request)
    # Then
    assert LostVoiceSession.commits == 1 and result.base_shard == 7
    assert await original.settle_voice(request) == result
    state = await original.get_voice_state(1)
    assert state is not None and state.next_grant_seq == 2 and state.prepared_random is None


@pytest.mark.asyncio
async def test_seq_survives_retention(sessions: async_sessionmaker[AsyncSession]) -> None:
    """grant詳細を回収してもseqを巻き戻さず、古い付与要求を再加算しない。"""
    # 非機能要件：90日履歴の寿命と未受取・計測状態の寿命を分離する。
    # Given
    repo = await prepared(sessions)
    end = NOW + timedelta(minutes=1)
    request = VoiceSettlement(1, 0, "epoch-a", 1, end, end)
    await repo.settle_voice(request)
    before = await repo.get_voice_state(1)
    # When
    result = await RetentionRepository(sessions, repo.gate).purge(end + timedelta(days=90))
    # Then
    assert result.grants == 1
    with pytest.raises(ValueError):
        await repo.settle_voice(request)
    assert await repo.get_voice_state(1) == before
    async with sessions() as session:
        assert list(await session.scalars(select(VoiceGrant))) == []
        pending = (await session.scalars(select(VoicePending))).one()
        assert pending.voice_shard == pending.power_meter == 7
