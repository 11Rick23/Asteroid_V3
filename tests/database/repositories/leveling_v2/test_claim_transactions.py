from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import Claim, PeriodRow, PeriodUser, VoicePending
from app.database.repositories.leveling_v2 import ClaimRequest, LevelingRepository, MessageAward, MutationGate

OCTOBER = datetime(2026, 10, 15, tzinfo=UTC)
NOVEMBER = datetime(2026, 11, 2, tzinfo=UTC)


@pytest.mark.asyncio
async def test_claim_race(sessions: async_sessionmaker[AsyncSession]) -> None:
    """手動と月末受取が競合しても未受取を一度だけ恒常へ反映する。"""
    # 非機能要件：別セッションの受取は二重付与せず、期間powerを増減しない。
    # Given
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=OCTOBER)
    await repo.award_message(MessageAward(1, 1, "text", OCTOBER, OCTOBER, 10))
    async with sessions() as session:
        month = (await session.scalars(select(PeriodRow).where(PeriodRow.kind == "month"))).one()
        month_id = month.period_id
        session.add(
            VoicePending(
                user_id=1, month_period_id=month_id, origin="native", voice_shard=250, bonus_shard=50, power_meter=300
            )
        )
        await session.commit()
    # 独立gateでもDB側の排他が成立することを確認する。
    other = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=OCTOBER)
    manual = ClaimRequest("manual:1", 1, "manual", NOVEMBER)
    automatic = ClaimRequest("month:1", 1, "month_close", NOVEMBER, month_id)
    # When
    results = await asyncio.gather(repo.claim(manual), other.claim(automatic))
    # Then
    assert sum(result.voice_shard for result in results) == 250
    assert sum(result.bonus_shard for result in results) == 50
    assert sum(result.power_released for result in results) == 300
    account = await repo.get_account(1)
    assert account is not None and account.growth.total == 310
    assert await repo.claim(manual) == results[0]
    async with sessions() as session:
        assert list(await session.scalars(select(PeriodUser.total_power))) == [10, 10, 10]
        claims = list(await session.scalars(select(Claim)))
        assert len(claims) == 2
        pending = (await session.scalars(select(VoicePending))).one()
        assert (pending.voice_shard, pending.bonus_shard, pending.power_meter) == (0, 0, 0)


@pytest.mark.asyncio
async def test_reject_early_close(sessions: async_sessionmaker[AsyncSession]) -> None:
    """月終了前の自動受取は拒否し、受取台帳を作らない。"""
    # 機能要件：DR07の暦月終了条件を受取入口でも守る。
    # Given
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=OCTOBER)
    await repo.award_message(MessageAward(1, 1, "text", OCTOBER, OCTOBER, 10))
    async with sessions() as session:
        month = (await session.scalars(select(PeriodRow).where(PeriodRow.kind == "month"))).one()
    # When / Then
    with pytest.raises(ValueError, match="月終了前"):
        await repo.claim(ClaimRequest("early", 1, "month_close", OCTOBER, month.period_id))
    async with sessions() as session:
        assert list(await session.scalars(select(Claim))) == []
