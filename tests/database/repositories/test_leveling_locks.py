from __future__ import annotations

import asyncio

import pytest

from app.database.repositories.leveling_locks import LevelingLocks


@pytest.mark.asyncio
async def test_migration_waits_for_both_users_without_blocking_unrelated_user():
    """複数ユーザーの移行ロックは両者の更新を待ち、無関係なユーザーを止めない。"""
    # 非機能要件：逆方向の移行と通常更新の競合を安全に処理する。
    # Given
    locks = LevelingLocks()
    entered = asyncio.Event()

    async def migration():
        async with locks.user_updates(2, 1):
            entered.set()

    # When / Then
    async with locks._user_update(2):
        task = asyncio.create_task(migration())
        await asyncio.sleep(0)
        assert not entered.is_set()
        async with locks._user_update(3):
            pass
    await asyncio.wait_for(task, timeout=1)
    assert entered.is_set()


@pytest.mark.asyncio
async def test_cancelled_reset_releases_waiting_updates():
    """移行終了を待つ月次リセットがキャンセルされても通常更新を再開できる。"""
    # 非機能要件：長い移行処理中のキャンセルでロックが残り続けることを防ぐ。
    # Given
    locks = LevelingLocks()

    async def reset():
        async with locks._monthly_power_reset():
            pass

    # When
    async with locks.user_updates(1, 2):
        task = asyncio.create_task(reset())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    # Then
    async def update():
        async with locks._user_update(1):
            pass

    await asyncio.wait_for(update(), timeout=1)
