from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import discord
import pytest

from app.database.account_migration import MigrationOptions
from app.database.leveling_state import ShardState
from app.features.account_migration import messages
from app.features.account_migration.discord_state import member_overwrite
from tests.support.discord_layout import layout_text


@pytest.mark.asyncio
async def test_departed_source_uses_saved_roles(world):
    """退会済みの移行元には保存済みロールを使い、メンバー不在でも個別権限を移せる。"""
    # 機能要件：旧アカウントが参加していなくても管理者が引き継げる。
    # Given
    source = Mock(spec=discord.User, id=1, bot=False)
    await world.bot.db.user_roles.save_user_roles(1, [10])
    world.channel.overwrites = {
        discord.Object(id=1, type=discord.User): discord.PermissionOverwrite(view_channel=True)
    }

    async def fetch_member(user_id):
        if user_id == 1:
            raise discord.NotFound(Mock(status=404, reason="Not Found"), "Unknown Member")
        return world.target

    world.guild.fetch_member.side_effect = fetch_member
    # When
    plan = await world.service.preview(world.guild, source, 2, MigrationOptions())
    result = await world.service.execute(world.guild, source, plan, world.record, 99)
    # Then
    assert result == messages.COMPLETED
    assert plan.discord.transferable_roles == (10,)
    world.target.add_roles.assert_awaited_once()
    assert member_overwrite(world.channel, 2) == (1024, 0)
    assert (await world.bot.db.user_roles.get_user_roles(1)) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["hierarchy", "managed", "permission"])
async def test_unassignable_roles_are_skipped(world, reason):
    """操作できないロールを明示して残し、操作可能なロールとレベリングを移行する。"""
    # 機能要件：ロールの操作権限不足で他のデータの移行を止めない。
    # 非機能要件：除外したロールと保存済みロールを移行元から削除しない。
    # Given
    await world.bot.db.leveling_state.set_shards(1, ShardState(100))
    await world.bot.db.user_roles.save_user_roles(1, [10, 20])
    if reason == "hierarchy":
        world.roles[10].is_assignable.return_value = False
    elif reason == "managed":
        world.roles[10].managed = True
    else:
        world.guild.me.guild_permissions = discord.Permissions.none()
    excluded = (10, 20) if reason == "permission" else (10,)
    # When
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    fields = messages.preview_fields(plan.source, plan.target, plan.options, plan.discord)
    result = await world.service.execute(world.guild, world.source, plan, world.record, 99)
    # Then
    assert result == messages.COMPLETED
    assert plan.discord.skipped_roles == excluded
    assert plan.discord.transferable_roles == (() if reason == "permission" else (20,))
    assert any(name.startswith("⏭️ 除外ロール") and "<@&10>" in value for name, value, _ in fields)
    assert {role.id for role in world.source.roles} == set(excluded)
    assert {role.id for role in world.target.roles} == {20, 30}
    assert {role.role_id for role in await world.bot.db.user_roles.get_user_roles(1)} == set(excluded)
    source, target = await world.bot.db.account_migration.read_pair(1, 2)
    assert source.shards.total == 0
    assert target.shards == ShardState(100)
    assert world.roles[10] not in [call.args[0] for call in world.source.remove_roles.await_args_list]
    assert world.roles[10] not in [call.args[0] for call in world.target.add_roles.await_args_list]


@pytest.mark.asyncio
async def test_only_excluded_roles_are_shown(world):
    """全ロールが対象外でも、空データのエラーにせず除外対象を表示する。"""
    # 機能要件：ロールだけを選択した場合も除外されるロールを確認できる。
    # Given
    world.guild.me.guild_permissions = discord.Permissions.none()
    # When
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions(False, True, False, False))
    result = await world.service.execute(world.guild, world.source, plan, world.record, 99)
    # Then
    assert plan.discord.skipped_roles == (10, 20)
    fields = messages.preview_fields(plan.source, plan.target, plan.options, plan.discord)
    assert ("🏷️ ロール", "**0件**を引き継ぎ", True) in fields
    assert ("⏭️ 除外ロール · 2件", "<@&10> <@&20>", False) in fields
    assert result == messages.COMPLETED
    world.source.remove_roles.assert_not_awaited()
    world.target.add_roles.assert_not_awaited()


@pytest.mark.asyncio
async def test_role_permissions_changed_after_preview(world):
    """プレビュー後に操作できるロールが変わったら、移行前に再確認を求める。"""
    # 非機能要件：ユーザーが確認した除外対象を確定時に黙って変更しない。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    world.roles[10].is_assignable.return_value = False
    # When / Then
    with pytest.raises(ValueError, match="stale"):
        await world.service.execute(world.guild, world.source, plan, world.record, 99)
    world.target.add_roles.assert_not_awaited()
    world.channel.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_target_only_permissions_are_preserved(world):
    """移行元に設定のないフリカテでは、移行先の個別設定を保持する。"""
    # 機能要件：移行先にだけある設定は操作権限の有無にかかわらず変更しない。
    # Given
    world.channel.overwrites.pop(world.source)
    world.channel.permissions_for.return_value = discord.Permissions.none()
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    # When
    await world.service.execute(world.guild, world.source, plan, world.record, 99)
    # Then
    assert plan.discord.permissions == ()
    assert member_overwrite(world.channel, 2) == (0, 2048)
    world.channel.set_permissions.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("source_view", [True, False, None])
async def test_permission_conflicts_prefer_source(world, source_view):
    """許可・拒否が競合する項目だけ移行元を優先し、未設定の項目は移行先を保持する。"""
    # 機能要件：権限の項目ごとに設定を引き継ぎ、移行元の個別設定を削除する。
    # Given
    world.channel.overwrites[world.source] = discord.PermissionOverwrite(view_channel=source_view)
    world.channel.overwrites[world.target] = discord.PermissionOverwrite(
        view_channel=not source_view if source_view is not None else True,
        send_messages=False,
    )
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    # When
    result = await world.service.execute(world.guild, world.source, plan, world.record, 99)
    # Then
    assert result == messages.COMPLETED
    actual = world.channel.overwrites[world.target]
    assert actual.view_channel is (source_view if source_view is not None else True)
    assert actual.send_messages is False
    assert member_overwrite(world.channel, 1) is None
    assert plan.discord.permissions[0].migrated == member_overwrite(world.channel, 2)


@pytest.mark.asyncio
async def test_failure_to_finish_record_keeps_restore_message(world):
    """完了表示の更新に失敗しても、同じメッセージに保存した復元コマンドを保持する。"""
    # 非機能要件：移行結果と通知の失敗を区別する。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    world.record.edit = AsyncMock(
        side_effect=[world.record, discord.HTTPException(Mock(status=500, reason="error"), "failed")]
    )
    # When
    result = await world.service.execute(world.guild, world.source, plan, world.record, 99)
    # Then
    assert result == messages.RECORD_FAILED
    assert "/leveling shard set" in layout_text(world.record.edit.await_args_list[0].kwargs["view"])
    world.channel.send.assert_not_awaited()
    assert {role.id for role in world.target.roles} == {10, 20, 30}
