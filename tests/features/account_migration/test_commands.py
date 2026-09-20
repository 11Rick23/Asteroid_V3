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
from app.features.account_migration.cog import migrate, setup
from app.features.account_migration.presentation import MigrationCheckView, MigrationStatusView
from app.features.account_migration.views import MigrationView
from app.features.leveling.commands.pending_command import set_pending
from tests.support.discord_layout import layout_text


def test_flags_and_command_metadata():
    """移行コマンドは管理者用に登録し、全種類の移行を初期値で有効にする。"""
    # 機能要件：全引数に説明文があり、機能フラグで読み込みを制御できる。
    # Given / When / Then
    assert "app.features.account_migration.cog" in list(iter_enabled_extensions(AsteroidConfig()))
    disabled = AsteroidConfig(features=FeatureFlags(account_migration=False))
    assert "app.features.account_migration.cog" not in list(iter_enabled_extensions(disabled))
    assert migrate.guild_only
    assert migrate.default_permissions and migrate.default_permissions.administrator
    assert migrate.parent is None
    assert migrate.qualified_name == "migrate"
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
    assert registry == {"migrate": migrate}


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
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True
    world.channel.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_double_confirmation_runs_once(world):
    """確定ボタンを同時に押しても移行を一度だけ実行する。"""
    # 非機能要件：遅延したボタン応答による二重移行を防ぐ。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    service = Mock(execute=AsyncMock(wraps=world.service.execute))
    view = MigrationView(service, world.source, plan, 1)
    interaction = SimpleNamespace(
        client=world.bot,
        guild_id=100,
        guild=world.guild,
        channel=world.channel,
        message=world.record,
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
    assert service.execute.call_args.args[3] is interaction.message
    world.channel.send.assert_not_awaited()
    interaction.edit_original_response.assert_not_awaited()
    interaction.followup.send.assert_awaited_once_with(messages.USED, ephemeral=True)
    assert interaction.response.defer.call_args.kwargs["ephemeral"] is False
    edits = world.record.edit.await_args_list
    assert len(edits) == 2
    for call, status in zip(edits, (messages.PROCESSING, messages.COMPLETED), strict=True):
        assert isinstance(call.kwargs["view"], MigrationStatusView)
        assert status in layout_text(call.kwargs["view"])
        assert "/leveling shard set" in layout_text(call.kwargs["view"])
    assert edits[0].kwargs["attachments"][0].filename == "account-migration.txt"


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
    payload = interaction.response.edit_message.call_args.kwargs
    assert payload["content"] is None and payload["embed"] is None
    assert isinstance(payload["view"], MigrationStatusView)
    assert messages.CANCELLED in layout_text(payload["view"])
    assert payload["attachments"][0].filename == "account-migration.txt"


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [True, False])
async def test_command_response_visibility(world, enabled):
    """プレビューは公開し、入力エラーは実行者だけに表示する。"""
    # 機能要件：公開する確認内容とephemeralのエラーを分ける。
    # Given
    interaction = SimpleNamespace(
        client=world.bot,
        guild=world.guild,
        channel=world.channel,
        user=world.source,
        response=SimpleNamespace(defer=AsyncMock(), send_message=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
        delete_original_response=AsyncMock(),
        edit_original_response=AsyncMock(),
    )
    original_read_pair = world.bot.db.account_migration.read_pair

    async def read_pair(*args):
        interaction.response.send_message.assert_awaited_once()
        return await original_read_pair(*args)

    world.bot.db.account_migration.read_pair = AsyncMock(side_effect=read_pair)
    # When
    await migrate.callback(
        cast(discord.Interaction, interaction), world.source, world.target, enabled, enabled, enabled, enabled
    )
    # Then
    interaction.response.defer.assert_not_awaited()
    world.channel.send.assert_not_awaited()
    interaction.delete_original_response.assert_not_awaited()
    initial = interaction.response.send_message.call_args.kwargs
    assert initial["ephemeral"] is False
    assert isinstance(initial["view"], MigrationCheckView)
    assert messages.CHECKING in layout_text(initial["view"])
    response = interaction.edit_original_response.call_args
    if enabled:
        assert response.kwargs["allowed_mentions"].to_dict()["parse"] == []
        assert isinstance(response.kwargs["view"], MigrationView)
        assert response.kwargs["view"].has_components_v2()
        assert response.kwargs["view"].actor_id == world.source.id
        assert response.kwargs["attachments"][0].filename == "account-migration.txt"
        interaction.followup.send.assert_not_awaited()
    else:
        assert messages.STOPPED in layout_text(response.kwargs["view"])
        interaction.followup.send.assert_awaited_once_with(messages.ERRORS["disabled"], ephemeral=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("result", ["stale", messages.FAILED])
async def test_confirmation_errors_are_private(world, result):
    """確定時のエラーを実行者へ通知し、保存済みの移行結果を別の表示で上書きしない。"""
    # 機能要件：再確認の案内と実行失敗をephemeralにする。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    execute = AsyncMock(side_effect=ValueError("stale")) if result == "stale" else AsyncMock(return_value=result)
    service = Mock(execute=execute)
    view = MigrationView(service, world.source, plan, 1)
    interaction = SimpleNamespace(
        client=world.bot,
        guild_id=100,
        guild=world.guild,
        channel=world.channel,
        message=world.record,
        user=world.source,
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
        edit_original_response=AsyncMock(),
    )
    # When
    await view.confirm.callback(cast(discord.Interaction, interaction))
    # Then
    expected = messages.ERRORS["stale"] if result == "stale" else result
    interaction.followup.send.assert_awaited_once_with(expected, ephemeral=True)
    if result == "stale":
        payload = interaction.edit_original_response.call_args.kwargs
        assert isinstance(payload["view"], MigrationStatusView)
        assert expected not in layout_text(payload["view"])
        assert messages.STOPPED in layout_text(payload["view"])
    else:
        interaction.edit_original_response.assert_not_awaited()
    world.channel.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_repeated_cancel_is_private(world):
    """処理済みの確認画面への操作はephemeralで案内する。"""
    # 機能要件：重複操作の案内をチャンネルに残さない。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    view = MigrationView(world.service, world.source, plan, 1)
    view.used = True
    interaction = SimpleNamespace(
        client=world.bot,
        guild_id=100,
        user=world.source,
        response=SimpleNamespace(send_message=AsyncMock()),
    )
    # When
    await view.cancel.callback(cast(discord.Interaction, interaction))
    # Then
    interaction.response.send_message.assert_awaited_once_with(messages.USED, ephemeral=True)
