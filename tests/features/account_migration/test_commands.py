from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from app.core.bot import AsteroidBot
from app.core.config import AsteroidConfig, FeatureFlags
from app.core.extensions import iter_enabled_extensions
from app.database.account_migration import MigrationOptions
from app.features.account_migration import messages
from app.features.account_migration.cog import account_group, migrate, setup
from app.features.account_migration.views import MigrationView
from app.features.leveling.commands.pending_command import set_pending


def test_flags_and_command_metadata():
    """移行コマンドは管理者用に登録し、全種類の移行を初期値で有効にする。"""
    # 機能要件：全引数に説明文があり、機能フラグで読み込みを制御できる。
    # Given / When / Then
    assert "app.features.account_migration.cog" in list(iter_enabled_extensions(AsteroidConfig()))
    disabled = AsteroidConfig(features=FeatureFlags(account_migration=False))
    assert "app.features.account_migration.cog" not in list(iter_enabled_extensions(disabled))
    assert account_group.guild_only
    assert account_group.default_permissions and account_group.default_permissions.administrator
    assert migrate.checks
    assert all(parameter.description and parameter.description != "…" for parameter in migrate.parameters)
    assert all(parameter.default is True for parameter in migrate.parameters[2:])
    assert all(parameter.required for parameter in set_pending.parameters)


@pytest.mark.asyncio
async def test_setup_registers_once():
    """拡張の再読込でコマンドを重複登録しない。"""
    # 非機能要件：既存の登録パターンを維持する。
    # Given
    registry = {}
    bot = SimpleNamespace(
        tree=SimpleNamespace(get_command=registry.get, add_command=lambda group: registry.update({group.name: group}))
    )
    # When
    await setup(cast(AsteroidBot, bot))
    await setup(cast(AsteroidBot, bot))
    # Then
    assert registry == {"account": account_group}


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["different_actor", "revoked_admin", "outside_guild"])
async def test_confirm_authorization(world, scenario):
    """確定時に実行者・管理者権限・運用サーバーを再検証する。"""
    # 非機能要件：プレビューを作成した権限だけでは移行を実行できない。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    view = MigrationView(world.service, world.source, plan, 1)
    user = world.source
    if scenario == "revoked_admin":
        user.guild_permissions = discord.Permissions.none()
    interaction = SimpleNamespace(
        client=world.bot,
        guild_id=200 if scenario == "outside_guild" else 100,
        user=world.target if scenario == "different_actor" else user,
        response=SimpleNamespace(send_message=AsyncMock(), is_done=lambda: False),
    )
    # When / Then
    assert not await view.interaction_check(cast(discord.Interaction, interaction))
    interaction.response.send_message.assert_awaited_once()
    world.channel.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_double_confirmation_runs_once(world):
    """確定ボタンを同時に押しても移行を一度だけ実行する。"""
    # 非機能要件：遅延したボタン応答による二重移行を防ぐ。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    service = Mock(execute=AsyncMock(return_value=messages.COMPLETED))
    view = MigrationView(service, world.source, plan, 1)
    interaction = SimpleNamespace(
        client=world.bot,
        guild_id=100,
        guild=world.guild,
        channel=world.channel,
        user=world.source,
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
        edit_original_response=AsyncMock(),
    )
    # When
    await asyncio.gather(
        view.confirm.callback(cast(discord.Interaction, interaction)),
        view.confirm.callback(cast(discord.Interaction, interaction)),
    )
    # Then
    service.execute.assert_awaited_once()
    interaction.followup.send.assert_awaited_once_with(messages.USED, ephemeral=True)


@pytest.mark.asyncio
async def test_cancel_does_not_execute(world):
    """キャンセルするとデータを変更せず、確認画面を閉じる。"""
    # 機能要件：確定前に移行を取りやめられる。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    service = Mock(execute=AsyncMock())
    view = MigrationView(service, world.source, plan, 1)
    interaction = SimpleNamespace(
        client=world.bot, guild_id=100, user=world.source, response=SimpleNamespace(edit_message=AsyncMock())
    )
    # When
    await view.cancel.callback(cast(discord.Interaction, interaction))
    # Then
    assert view.used
    service.execute.assert_not_awaited()
    interaction.response.edit_message.assert_awaited_once()
