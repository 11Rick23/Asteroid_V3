from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import discord
import pytest

from app.database.account_migration import MigrationOptions
from app.features.account_migration import messages
from app.features.account_migration.discord_state import member_overwrite


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
    result = await world.service.execute(world.guild, source, plan, world.channel, 99)
    # Then
    assert result == messages.COMPLETED
    assert plan.discord.transferable_roles == (10,)
    world.target.add_roles.assert_awaited_once()
    assert member_overwrite(world.channel, 2) == (1024, 0)
    assert (await world.bot.db.user_roles.get_user_roles(1)) == []


@pytest.mark.asyncio
async def test_unassignable_role_rejected_managed_role_skipped(world):
    """通常ロールを操作できなければ拒否し、連携管理ロールは対象外として明示する。"""
    # 非機能要件：付与できないロールを移行済みとして扱わない。
    # Given
    world.roles[10].is_assignable.return_value = False
    # When / Then
    with pytest.raises(ValueError, match="roles"):
        await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    world.roles[10].managed = True
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    assert plan.discord.skipped_roles == (10,)
    assert plan.discord.transferable_roles == (20,)


@pytest.mark.asyncio
async def test_target_only_permissions_are_removed(world):
    """移行元に設定のないフリカテでは、移行先の個別設定を削除する。"""
    # 機能要件：フリカテ権限は合算せず、移行元の設定で上書きする。
    # Given
    world.channel.overwrites.pop(world.source)
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    # When
    await world.service.execute(world.guild, world.source, plan, world.channel, 99)
    # Then
    assert member_overwrite(world.channel, 2) is None


@pytest.mark.asyncio
async def test_failure_to_finish_record_keeps_restore_message(world):
    """完了表示の更新に失敗しても、処理前に送った復元コマンドを保持する。"""
    # 非機能要件：移行結果と通知の失敗を区別する。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    world.record.edit = AsyncMock(side_effect=discord.HTTPException(Mock(status=500, reason="error"), "failed"))
    # When
    result = await world.service.execute(world.guild, world.source, plan, world.channel, 99)
    # Then
    assert result == messages.RECORD_FAILED
    assert "/leveling shard set" in world.channel.send.call_args.args[0]
    assert {role.id for role in world.target.roles} == {10, 20, 30}
