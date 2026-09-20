from __future__ import annotations

from datetime import date, datetime
from typing import cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.account_migration import AccountState, MigrationOptions, PendingState, merge_leveling
from app.database.leveling_state import MAX_POWER, MAX_TOTAL_SHARD, PowerState, ShardState
from app.database.models.leveling_hotness import LevelingHotnessEventModel
from tests.support.sqlite_database import SQLiteDatabase


@pytest.mark.asyncio
async def test_moves_all_database_data():
    """数量・履歴・未受取XPを合算し、誕生日を上書きして移行元から移動する。"""
    # 機能要件：移行前の両アカウントの合計を保存し、再適用しても二重加算しない。
    # Given
    db = SQLiteDatabase()
    await db.leveling_state.set_shards(1, ShardState(100, 200, 300))
    await db.leveling_state.set_shards(2, ShardState(10, 20, 30))
    await db.leveling_state.set_powers(1, PowerState(40, 50, 60))
    await db.account_migration.set_pending(1, PendingState(7, 8, 9, True, False))
    await db.user_birthdays.upsert_data(1, date(2000, 2, 29))
    await db.user_birthdays.upsert_data(2, date(2000, 1, 1))
    await db.user_roles.save_user_roles(1, [10])
    async with db.session() as session:
        session.add(LevelingHotnessEventModel(user_id=1, amount=100, earned_at=datetime(2026, 9, 20)))
        await session.commit()
    # When
    source, target = await db.account_migration.read_pair(1, 2)
    async with db.session() as session:
        await db.account_migration.apply(cast(AsyncSession, session), source, target, MigrationOptions(), (10, 20), ())
        await session.commit()
    # Then
    empty, result = await db.account_migration.read_pair(1, 2)
    assert empty == AccountState(1)
    assert result.shards == ShardState(110, 220, 330)
    assert result.powers == PowerState(40, 50, 60)
    assert result.pending == PendingState(7, 8, 9, True, False)
    assert result.birthday == date(2000, 2, 29)
    assert result.saved_roles == (10, 20)
    async with db.session() as session:
        events = list(await session.scalars(select(LevelingHotnessEventModel)))
        assert [(event.user_id, event.amount, event.earned_at) for event in events] == [
            (2, 100, datetime(2026, 9, 20))
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize("commit", [True, False])
async def test_birthday_only_and_rollback(commit):
    """無効な種類のデータは変更せず、未確定の移行はまとめて巻き戻せる。"""
    # 非機能要件：対象外のデータと失敗前の状態を維持する。
    # Given
    db = SQLiteDatabase()
    await db.leveling_state.set_shards(1, ShardState(100, 0, 0))
    await db.user_birthdays.upsert_data(2, date(2000, 1, 1))
    source, target = await db.account_migration.read_pair(1, 2)
    # When
    async with db.session() as session:
        await db.account_migration.apply(
            cast(AsyncSession, session), source, target, MigrationOptions(False, False, True, False), (), ()
        )
        if commit:
            await session.commit()
    # Then
    actual_source, actual_target = await db.account_migration.read_pair(1, 2)
    assert actual_source == source
    assert actual_target.birthday == (None if commit else target.birthday)


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (AccountState(1, shards=ShardState(MAX_TOTAL_SHARD, 0, 0)), AccountState(2, shards=ShardState(1, 0, 0))),
        (AccountState(1, powers=PowerState(MAX_POWER, 0, 0)), AccountState(2, powers=PowerState(1, 0, 0))),
        (AccountState(1, pending=PendingState(MAX_POWER, 0, 0)), AccountState(2, pending=PendingState(1, 0, 0))),
        (AccountState(1, shards=ShardState(MAX_TOTAL_SHARD, 0, 0)), AccountState(2, pending=PendingState(1, 0, 0))),
    ],
)
def test_rejects_overflow(source, target):
    """合算値と未受取XPの受取後の値が上限を超える移行は拒否する。"""
    # 非機能要件：Discordを変更する前にDB上限超過を検出する。
    # Given / When / Then
    with pytest.raises(ValueError):
        merge_leveling(source, target)


@pytest.mark.asyncio
async def test_pending_set_restores_flags_and_zero():
    """未受取XPと通知状態を絶対値で復元し、0に戻せる。"""
    # 機能要件：復元コマンドで未受取分も復元できる。
    # Given
    db = SQLiteDatabase()
    values = PendingState(100, 200, 300, True, True)
    # When / Then
    await db.account_migration.set_pending(1, values)
    assert (await db.account_migration.read_pair(1, 2))[0].pending == values
    await db.account_migration.set_pending(1, PendingState())
    assert (await db.account_migration.read_pair(1, 2))[0].pending == PendingState()
