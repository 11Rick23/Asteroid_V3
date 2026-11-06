from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import Account
from app.database.repositories.leveling_v2.messages import MessageAward, apply_message, find_message
from app.database.repositories.leveling_v2.storage import add_growth
from app.database.repositories.leveling_v2.transaction import CommitUnknown, Resolution, Transactions

NOW = datetime(2026, 10, 15, tzinfo=UTC)


class LostCommitSession(AsyncSession):
    async def commit(self) -> None:
        await super().commit()
        raise OperationalError("COMMIT", {}, Exception(2013, "injected lost response"))


class UnconfirmedCommitSession(AsyncSession):
    async def commit(self) -> None:
        await self.rollback()
        raise OperationalError("COMMIT", {}, Exception(2013, "injected lost response"))


@pytest.mark.asyncio
async def test_committed_response_lost(sessions: async_sessionmaker[AsyncSession]) -> None:
    """commit済みで応答だけ失われた場合は別セッションのキー照会で結果を返す。"""
    # 非機能要件：commit結果不明時に加算処理を再実行しない。
    # Given
    failing = async_sessionmaker(sessions.kw["bind"], class_=LostCommitSession, expire_on_commit=False)
    calls = 0

    async def action(session: AsyncSession):
        nonlocal calls
        calls += 1
        return await apply_message(session, MessageAward(1, 1, "text", NOW, NOW, 10), NOW)

    # When
    result = await Transactions(failing).run(action, lambda session: find_message(session, 1, NOW))
    # Then
    assert calls == 1 and result.base_shard == 10
    async with sessions() as session:
        row = await session.get(Account, 1)
        assert row is not None and row.text_shard == 10


@pytest.mark.asyncio
async def test_missing_is_unknown(sessions: async_sessionmaker[AsyncSession]) -> None:
    """commit応答喪失後の非存在だけで安全な再実行と判断しない。"""
    # 非機能要件：遅延commitの可能性がある場合は結果不明を呼出し側へ返す。
    # Given
    failing = async_sessionmaker(sessions.kw["bind"], class_=UnconfirmedCommitSession, expire_on_commit=False)
    calls = 0

    async def action(session: AsyncSession):
        nonlocal calls
        calls += 1
        return await apply_message(session, MessageAward(1, 1, "text", NOW, NOW, 10), NOW)

    # When / Then
    with pytest.raises(CommitUnknown):
        await Transactions(failing).run(action, lambda session: find_message(session, 1, NOW))
    assert calls == 1
    async with sessions() as session:
        assert await session.get(Account, 1) is None


@pytest.mark.asyncio
async def test_real_deadlock_retry(sessions: async_sessionmaker[AsyncSession]) -> None:
    """InnoDBの実deadlockではtx全体を再試行して両操作を一度ずつ反映する。"""
    # 非機能要件：エラー番号1213を受けた途中更新を残さず、同じ要求で再試行する。
    # Given
    async with sessions() as session:
        session.add_all([Account(user_id=1), Account(user_id=2)])
        await session.commit()
    barrier = asyncio.Barrier(2)
    attempts = [0, 0]

    async def run(index: int):
        async def action(session: AsyncSession) -> int:
            attempts[index] += 1
            first, second = (1, 2) if index == 0 else (2, 1)
            row = (await session.scalars(select(Account).where(Account.user_id == first).with_for_update())).one()
            add_growth(row, text=1)
            await session.flush()
            if attempts[index] == 1:
                await barrier.wait()
            row = (await session.scalars(select(Account).where(Account.user_id == second).with_for_update())).one()
            add_growth(row, text=1)
            return index

        async def resolve(session: AsyncSession) -> Resolution[int]:
            return Resolution(False)

        return await Transactions(sessions).run(action, resolve)

    # When
    assert await asyncio.wait_for(asyncio.gather(run(0), run(1)), timeout=10) == [0, 1]
    # Then
    assert sum(attempts) == 3
    async with sessions() as session:
        assert list(await session.scalars(select(Account.text_shard).order_by(Account.user_id))) == [2, 2]


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [1205, 1213])
async def test_retry_limit(sessions: async_sessionmaker[AsyncSession], code: int) -> None:
    """lock timeout/deadlockが続く場合は3回で終了し、途中更新を残さない。"""
    # 非機能要件：同一入力の有限再試行だけを行う。
    # Given
    attempts = 0

    async def action(session: AsyncSession):
        nonlocal attempts
        attempts += 1
        await apply_message(session, MessageAward(1, 1, "text", NOW, NOW, 10), NOW)
        raise OperationalError("injected", {}, Exception(code, "injected lock failure"))

    # When / Then
    with pytest.raises(OperationalError):
        await Transactions(sessions).run(action, lambda session: find_message(session, 1, NOW))
    assert attempts == 3
    async with sessions() as session:
        assert await session.get(Account, 1) is None
