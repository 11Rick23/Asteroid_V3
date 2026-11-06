from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import Event, MessageReceipt, PeriodUser
from app.database.repositories.leveling_v2 import LevelingRepository, MessageAward, MutationGate, RetentionRepository
from app.database.repositories.leveling_v2.messages import apply_message, find_message
from app.database.repositories.leveling_v2.transaction import Transactions

NOW = datetime(2026, 10, 15, tzinfo=UTC)


@pytest.mark.asyncio
@pytest.mark.parametrize("purge_first", [False, True])
async def test_receipt_expiry(sessions: async_sessionmaker[AsyncSession], purge_first: bool) -> None:
    """期限内は延長せず重複拒否し、90日後は物理削除の有無によらず新generationで受理する。"""
    # 機能要件：DR01の有限保証と無期限遅延受付を両立する。
    # Given
    gate = MutationGate()
    repo = LevelingRepository(sessions, gate=gate, coverage_start_at=NOW)
    first = await repo.award_message(MessageAward(1, 1, "text", NOW, NOW, 10))
    expiry = NOW + timedelta(days=90)
    repeated = await repo.award_message(MessageAward(1, 1, "text", NOW, expiry - timedelta(microseconds=1), 100))
    assert first == repeated
    async with sessions() as session:
        receipt = await session.get(MessageReceipt, 1)
        assert receipt is not None and receipt.expires_at == expiry
    if purge_first:
        await RetentionRepository(sessions, gate).purge(expiry)
    # When
    second = await repo.award_message(MessageAward(1, 1, "text", NOW, expiry, 10))
    # Then
    assert second.operation_key != first.operation_key
    account = await repo.get_account(1)
    assert account is not None and account.text_shard == 20
    async with sessions() as session:
        assert list(await session.scalars(select(PeriodUser.total_power))) == [20, 20, 20]


@pytest.mark.asyncio
async def test_cross_route_duplicate(sessions: async_sessionmaker[AsyncSession]) -> None:
    """text/actionの異なるルートでも同じmessage IDは一度だけ確定する。"""
    # 非機能要件：独立session間のルート競合で重複キーを分離しない。
    # Given
    barrier = asyncio.Barrier(2)

    async def run(kind: str):
        initial = True

        async def action(session: AsyncSession):
            nonlocal initial
            if initial:
                initial = False
                await barrier.wait()
            return await apply_message(session, MessageAward(1, 1, kind, NOW, NOW, 10), NOW)

        return await Transactions(sessions).run(action, lambda session: find_message(session, 1, NOW))

    # When
    first, second = await asyncio.wait_for(asyncio.gather(run("text"), run("action")), timeout=10)
    # Then
    assert first == second
    async with sessions() as session:
        assert len(list(await session.scalars(select(Event)))) == 1
        assert list(await session.scalars(select(PeriodUser.total_power))) == [10, 10, 10]
