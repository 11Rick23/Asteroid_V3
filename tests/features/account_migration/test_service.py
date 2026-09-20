from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.database.account_migration import MigrationOptions
from app.database.leveling_state import ShardState
from app.features.account_migration import messages
from app.features.account_migration.discord_state import member_overwrite


@pytest.mark.asyncio
async def test_preview_confirm_and_restore_record(world):
    """プレビューは読み取りだけで、確定後に数量・ロール・誕生日・権限を移動して復元コマンドを記録する。"""
    # 機能要件：合算と上書きを区別し、確定ボタンより前に変更しない。
    # Given
    await world.bot.db.leveling_state.set_shards(1, ShardState(100, 200, 300))
    await world.bot.db.leveling_state.set_shards(2, ShardState(10, 20, 30))
    await world.bot.db.user_birthdays.upsert_data(1, date(2000, 2, 29))
    # When
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    # Then
    world.source.remove_roles.assert_not_awaited()
    world.target.add_roles.assert_not_awaited()
    world.channel.set_permissions.assert_not_awaited()
    assert ("💎 シャード", "60 → **660**", True) in messages.preview_fields(
        plan.source, plan.target, plan.options, plan.discord
    )
    assert "110/220/330" in messages.details(plan.source, plan.target, plan.discord, plan.options)
    # When
    result = await world.service.execute(world.guild, world.source, plan, world.channel, 99)
    # Then
    assert result == messages.COMPLETED
    source, target = await world.bot.db.account_migration.read_pair(1, 2)
    assert source.shards.total == 0
    assert target.shards == ShardState(110, 220, 330)
    assert target.birthday == date(2000, 2, 29)
    assert {role.id for role in world.source.roles} == set()
    assert {role.id for role in world.target.roles} == {10, 20, 30}
    assert member_overwrite(world.channel, 1) is None
    assert member_overwrite(world.channel, 2) == (1024, 0)
    record = world.record.edit.call_args.kwargs["content"]
    assert "/leveling shard set ユーザー:1 テキスト:100 ボイス:200 ボーナス:300" in record
    assert "/leveling shard set ユーザー:2 テキスト:10 ボイス:20 ボーナス:30" in record
    assert "/leveling pending set" in record
    assert len(record) < 2000
    # 再度同じ内容を確定しても二重に合算しない。
    with pytest.raises(ValueError, match="stale"):
        await world.service.execute(world.guild, world.source, plan, world.channel, 99)


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["shards", "roles", "permissions"])
async def test_stale_preview_has_no_side_effects(world, change):
    """プレビュー後の数量・ロール・権限変更を検出すると移行を実行しない。"""
    # 非機能要件：確定対象は表示された内容と一致しなければならない。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    if change == "shards":
        await world.bot.db.leveling_state.set_shards(1, ShardState(1))
    elif change == "roles":
        world.source.roles = []
    else:
        world.channel.overwrites = {}
    # When / Then
    with pytest.raises(ValueError, match="stale"):
        await world.service.execute(world.guild, world.source, plan, world.channel, 99)
    world.channel.send.assert_not_awaited()
    world.target.add_roles.assert_not_awaited()


@pytest.mark.asyncio
async def test_disabled_options_are_untouched(world):
    """レベリングだけの移行では誕生日・ロール・個別権限を変更しない。"""
    # 機能要件：各移行対象を独立して無効化できる。
    # Given
    await world.bot.db.leveling_state.set_shards(1, ShardState(100))
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions(True, False, False, False))
    await world.bot.db.user_birthdays.upsert_data(2, date(2000, 3, 4))
    # When
    result = await world.service.execute(world.guild, world.source, plan, world.channel, 99)
    # Then
    assert result == messages.COMPLETED
    world.channel.set_permissions.assert_not_awaited()
    world.target.add_roles.assert_not_awaited()
    assert (await world.bot.db.account_migration.read_pair(1, 2))[1].birthday == date(2000, 3, 4)


@pytest.mark.asyncio
async def test_logging_failure_stops_before_changes(world):
    """復元記録を送れない場合は移行を開始しない。"""
    # 非機能要件：移行前の数量が記録されないまま失われることを防ぐ。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    world.channel.send.side_effect = RuntimeError("send failed")
    # When / Then
    with pytest.raises(RuntimeError, match="send failed"):
        await world.service.execute(world.guild, world.source, plan, world.channel, 99)
    world.target.add_roles.assert_not_awaited()
    world.channel.set_permissions.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["discord", "database"])
async def test_failure_rolls_back_discord_and_database(world, failure):
    """Discord操作やDB保存の失敗時は、それまでの変更を巻き戻す。"""
    # 非機能要件：複数リソースの移行が途中で止まっても、復元できたかを正確に通知する。
    # Given
    await world.bot.db.leveling_state.set_shards(1, ShardState(100))
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    if failure == "discord":
        original = world.channel.set_permissions.side_effect
        calls = 0

        async def fail_once(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("permission failed")
            return await original(*args, **kwargs)

        world.channel.set_permissions.side_effect = fail_once
    else:
        original_apply = world.bot.db.account_migration.apply

        async def fail_after_write(*args, **kwargs):
            await original_apply(*args, **kwargs)
            raise RuntimeError("write failed")

        world.bot.db.account_migration.apply = AsyncMock(side_effect=fail_after_write)
    # When
    result = await world.service.execute(world.guild, world.source, plan, world.channel, 99)
    # Then
    assert result == messages.FAILED
    assert {role.id for role in world.source.roles} == {10, 20}
    assert {role.id for role in world.target.roles} == {20, 30}
    assert member_overwrite(world.channel, 1) == (1024, 0)
    assert member_overwrite(world.channel, 2) == (0, 2048)
    assert (await world.bot.db.account_migration.read_pair(1, 2))[0].shards == ShardState(100)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("options", "code"),
    [
        (MigrationOptions(False, False, False, False), "disabled"),
        (MigrationOptions(True, False, False, False), "empty"),
    ],
)
async def test_invalid_selection(world, options, code):
    """全対象オフや空の移行元ではプレビューを作成しない。"""
    # 非機能要件：移行元が空の再実行による移行先データの消去を防ぐ。
    # Given / When / Then
    with pytest.raises(ValueError, match=code):
        await world.service.preview(world.guild, world.source, 2, options)


@pytest.mark.asyncio
async def test_rollback_failure_is_reported(world):
    """ロールを復元できなかった場合は、巻き戻し成功と通知しない。"""
    # 非機能要件：手動復元が必要な状態を記録する。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    world.bot.db.account_migration.apply = AsyncMock(side_effect=RuntimeError("write failed"))
    world.source.add_roles.side_effect = RuntimeError("restore failed")
    # When
    result = await world.service.execute(world.guild, world.source, plan, world.channel, 99)
    # Then
    assert result == messages.ROLLBACK_FAILED
    assert messages.ROLLBACK_FAILED in world.record.edit.call_args.kwargs["content"]


@pytest.mark.asyncio
async def test_commit_failure_is_reported_as_uncertain(world):
    """COMMITの結果が不明な場合は、Discordだけを巻き戻したり完了と断定したりしない。"""
    # 非機能要件：通信切断によるDB確定結果不明を記録し、安易な再実行を促さない。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    original_apply = world.bot.db.account_migration.apply

    async def break_commit(session, *args, **kwargs):
        await original_apply(session, *args, **kwargs)
        session.commit.side_effect = RuntimeError("connection lost")

    world.bot.db.account_migration.apply = AsyncMock(side_effect=break_commit)
    # When
    result = await world.service.execute(world.guild, world.source, plan, world.channel, 99)
    # Then
    assert result == messages.COMMIT_UNCERTAIN
    assert {role.id for role in world.target.roles} == {10, 20, 30}
    assert messages.COMMIT_UNCERTAIN in world.record.edit.call_args.kwargs["content"]


@pytest.mark.asyncio
async def test_cancelled_execution_restores_changes(world):
    """実行タスクが中断された場合も、確定前のDiscord変更を巻き戻す。"""
    # 非機能要件：キャンセル例外でも移行途中の変更を残さない。
    # Given
    import asyncio

    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    world.bot.db.account_migration.apply = AsyncMock(side_effect=asyncio.CancelledError())
    # When / Then
    with pytest.raises(asyncio.CancelledError):
        await world.service.execute(world.guild, world.source, plan, world.channel, 99)
    assert {role.id for role in world.source.roles} == {10, 20}
    assert {role.id for role in world.target.roles} == {20, 30}
    assert messages.FAILED in world.record.edit.call_args.kwargs["content"]
