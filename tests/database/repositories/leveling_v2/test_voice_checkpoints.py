from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import Channel
from app.database.repositories.leveling_v2 import LevelingRepository, MutationGate
from app.database.repositories.leveling_v2.transaction import VersionConflict
from app.database.repositories.leveling_v2.voice_state import Checkpoint
from app.features.leveling.domain.voice_time import VoiceSegment

NOW = datetime(2026, 10, 15, tzinfo=UTC)


@pytest.mark.asyncio
async def test_cas_competition(sessions: async_sessionmaker[AsyncSession]) -> None:
    """同じexpected versionの更新は一方だけ成功し、古いepochを拒否する。"""
    # 非機能要件：独立セッション間でcheckpointを二重適用しない。
    # Given
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    other = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    initial = Checkpoint(1, None, None, "epoch-a", "tracking", NOW, None)
    saved = await repo.checkpoint(initial)
    request = replace(
        initial,
        expected_version=saved.checkpoint_version,
        expected_epoch="epoch-a",
        confirmed_at=NOW + timedelta(seconds=1),
    )
    # When
    results = await asyncio.gather(repo.checkpoint(request), other.checkpoint(request), return_exceptions=True)
    # Then
    assert sum(isinstance(result, VersionConflict) for result in results) == 1
    state = await repo.get_voice_state(1)
    assert state is not None and state.checkpoint_version == 1
    with pytest.raises(VersionConflict):
        await repo.checkpoint(replace(request, expected_version=1, expected_epoch="old-epoch"))


@pytest.mark.asyncio
async def test_resume_keeps_fraction(sessions: async_sessionmaker[AsyncSession]) -> None:
    """90日を超えた再開でも保存済み端数と固定乱数を失わない。"""
    # 機能要件：未精算区間・合算率・乱数を新epochで継続し、恒常へ未付与のまま保持する。
    # Given
    async with sessions() as session:
        session.add(Channel(channel_id=10, last_name="VC", kind="voice", last_seen_at=NOW))
        await session.commit()
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    part = VoiceSegment(NOW, NOW + timedelta(seconds=20), 10, rate_percent=10**70)
    first = await repo.checkpoint(
        Checkpoint(
            1,
            None,
            None,
            "epoch-a",
            "tracking",
            part.end,
            10,
            (part,),
            25,
        )
    )
    # When
    resumed = await repo.checkpoint(
        Checkpoint(
            1,
            first.checkpoint_version,
            "epoch-a",
            "epoch-b",
            "reconciling",
            NOW + timedelta(days=100),
            None,
        )
    )
    # Then
    assert resumed.segments == (part,)
    assert resumed.prepared_random == 25
    assert resumed.prepared_grant_seq == resumed.next_grant_seq == 1
    account = await repo.get_account(1)
    assert account is not None and account.growth.total == 0


@pytest.mark.asyncio
async def test_reject_overlap(sessions: async_sessionmaker[AsyncSession]) -> None:
    """確認済み時間の再投入を拒否してCAS versionを進めない。"""
    # 非機能要件：同じ既知区間を再計上できない。
    # Given
    async with sessions() as session:
        session.add(Channel(channel_id=10, last_name="VC", kind="voice", last_seen_at=NOW))
        await session.commit()
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    part = VoiceSegment(NOW, NOW + timedelta(seconds=20), 10)
    request = Checkpoint(1, None, None, "epoch-a", "tracking", part.end, 10, (part,), 25)
    saved = await repo.checkpoint(request)
    # When / Then
    with pytest.raises(ValueError, match="確認済み"):
        await repo.checkpoint(replace(request, expected_version=0, expected_epoch="epoch-a"))
    assert await repo.get_voice_state(1) == saved
