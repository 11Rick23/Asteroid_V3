from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import Account, Event, PeriodUser
from app.database.repositories.leveling_v2 import LevelingRepository, MessageAward, MutationGate
from app.database.repositories.leveling_v2.messages import apply_message, find_message
from app.database.repositories.leveling_v2.transaction import Transactions

NOW = datetime(2026, 10, 15, tzinfo=UTC)


def message(message_id: int) -> MessageAward:
    return MessageAward(message_id, 1, "text", NOW, NOW, 10)


@pytest.mark.asyncio
async def test_first_insert_race(sessions: async_sessionmaker[AsyncSession]) -> None:
    """独立セッションが同じユーザーを初回作成しても全加算が残る。"""
    # 非機能要件：アプリロック外の初回INSERT競合でもロストアップデートしない。
    # Given
    transactions = Transactions(sessions)
    barrier = asyncio.Barrier(8)

    async def award(message_id: int) -> None:
        await barrier.wait()
        await transactions.run(
            lambda session: apply_message(session, message(message_id), NOW),
            lambda session: find_message(session, message_id, NOW),
        )

    # When
    await asyncio.gather(*(award(i) for i in range(1, 9)))
    # Then
    async with sessions() as session:
        account = await session.get(Account, 1)
        assert account is not None and account.text_shard == 80
        assert list(await session.scalars(select(PeriodUser.total_power))) == [80, 80, 80]
        assert await session.scalar(select(func.count()).select_from(Event)) == 8


@pytest.mark.asyncio
async def test_same_message_race(sessions: async_sessionmaker[AsyncSession]) -> None:
    """同一メッセージの同時処理では一つの確定結果だけを返す。"""
    # 非機能要件：独立AsyncSession間でイベントと恒常・期間残高を二重加算しない。
    # Given
    transactions = Transactions(sessions)
    barrier = asyncio.Barrier(8)

    async def award():
        await barrier.wait()
        return await transactions.run(
            lambda session: apply_message(session, message(1), NOW),
            lambda session: find_message(session, 1, NOW),
        )

    # When
    results = await asyncio.gather(*(award() for _ in range(8)))
    # Then
    assert all(result == results[0] for result in results)
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    account = await repo.get_account(1)
    assert account is not None and account.text_shard == 10


@pytest.mark.asyncio
async def test_partial_failure(sessions: async_sessionmaker[AsyncSession]) -> None:
    """イベント保存後の例外でも期間・恒常・重複防止行をまとめて戻す。"""

    # 非機能要件：操作の一部だけをcommitしない。
    # Given
    async def fail(session: AsyncSession):
        await apply_message(session, message(1), NOW)
        raise RuntimeError("injected failure")

    # When
    with pytest.raises(RuntimeError, match="injected failure"):
        await Transactions(sessions).run(fail, lambda session: find_message(session, 1, NOW))
    # Then
    async with sessions() as session:
        assert await session.get(Account, 1) is None
        assert await session.scalar(select(func.count()).select_from(Event)) == 0
        assert await session.scalar(select(func.count()).select_from(PeriodUser)) == 0
        assert not (await find_message(session, 1, NOW)).found
