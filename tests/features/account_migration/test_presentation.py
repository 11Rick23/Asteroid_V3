from __future__ import annotations

import json
from dataclasses import replace

import discord
import pytest
from discord.http import handle_message_parameters

from app.database.account_migration import MigrationOptions
from app.features.account_migration import messages
from app.features.account_migration.presentation import MigrationStatusView
from app.features.account_migration.views import MigrationView
from tests.support.discord_layout import layout_text


@pytest.mark.asyncio
async def test_text_attachment_uses_names_and_ids(world):
    """txtはDiscordの装飾を含めず、名前・ID・復元コマンドを単独で読める。"""
    # 機能要件：メンションを展開できないプレーンテキストでも対象を識別できる。
    # Given
    world.source.display_name = "旧アカウント"
    world.target.display_name = "新アカウント"
    world.roles[10].name = "管理ロール"
    world.channel.name = "雑談部屋"
    world.roles[10].is_assignable.return_value = False
    # When
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    attachment = plan.detail_file()
    content = attachment.fp.read().decode("utf-8")
    # Then
    assert "移行元: 旧アカウント (ID: 1)" in content
    assert "移行先: 新アカウント (ID: 2)" in content
    assert "管理ロール (ID: 10)" in content
    assert "チャンネル: 雑談部屋 (ID: 500)" in content
    assert "[除外ロール（移行元に保持）]" in content
    assert "/leveling shard set ユーザー:1" in content
    assert "/leveling shard set ユーザー:2" in content
    for discord_syntax in ("<@", "<#", "**", "```", "###"):
        assert discord_syntax not in content
    attachment.close()


@pytest.mark.asyncio
async def test_preview_components_and_bounds_exclusions(world):
    """確認画面は数量・誕生日・権限を別欄にし、大量の除外ロールでも表示上限内に収める。"""
    # 機能要件：V2の確認画面で数量を比較でき、除外の全件はtxtで確認できる。
    # 非機能要件：DiscordのComponents V2の制限を超えない。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    ids = tuple(range(100000000000000001, 100000000000000251))
    plan = replace(plan, discord=replace(plan.discord, skipped_roles=ids))
    # When
    view = MigrationView(world.service, world.source, plan, 1)
    text = layout_text(view)
    content = messages.details(plan.source, plan.target, plan.discord, plan.options)
    # Then
    assert view.has_components_v2()
    assert "<@1>" in text and "<@2>" in text
    assert "💎 シャード" in text and "⚡ パワー" in text
    assert text.count("<@&") == 5
    assert "ほか245件" in text
    assert f"ID: {ids[-1]}" in content
    assert view.content_length() <= 4000
    assert view.total_children_count <= 40
    buttons = [item for item in view.walk_children() if isinstance(item, discord.ui.Button)]
    assert [button.label for button in buttons] == [messages.CONFIRM, messages.CANCEL]
    assert all(button.view is view for button in buttons)
    assert view.to_components()[-1]["type"] == discord.ComponentType.action_row.value
    assert view.timeout == 300


@pytest.mark.asyncio
async def test_record_mentions_do_not_notify_members(world):
    """公開した記録はメンションで対象を表示し、送信・更新とも通知を抑制する。"""
    # 非機能要件：結果の更新で実行者や移行対象へ重複通知を送らない。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    # When
    await world.service.execute(world.guild, world.source, plan, world.channel, 99)
    # Then
    for call in (world.channel.send.call_args, world.record.edit.call_args):
        assert call.kwargs["allowed_mentions"].to_dict()["parse"] == []
        assert "content" not in call.kwargs and "embed" not in call.kwargs
        assert isinstance(call.kwargs["view"], MigrationStatusView)
    record = layout_text(world.record.edit.call_args.kwargs["view"])
    assert "<@1> → <@2>" in record
    assert "実行者: <@99>" in record
    assert record.count("```") == 4
    assert "レベル復元用のコマンド" in record
    assert len(record) < 4000


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [messages.PROCESSING, messages.COMPLETED, messages.CANCELLED, messages.FAILED])
async def test_status_components_and_restore_commands(world, status):
    """処理状況・移行内容・復元コマンドをComponents V2の区切り付き表示で保存する。"""
    # 機能要件：処理中と処理後の両方で復元情報と添付にアクセスできる。
    # 非機能要件：テキストとコンポーネント数をDiscordの上限内に収める。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    # When
    view = MigrationStatusView(plan, 99, status, include_restore=True)
    # Then
    assert view.has_components_v2()
    assert status in layout_text(view)
    assert "レベル復元用のコマンド" in layout_text(view)
    assert "数量の復元" not in layout_text(view)
    assert sum(isinstance(item, discord.ui.Container) for item in view.children) == 2
    assert any(isinstance(item, discord.ui.Separator) for item in view.walk_children())
    files = [item for item in view.walk_children() if isinstance(item, discord.ui.File)]
    assert [item.media.url for item in files] == ["attachment://account-migration.txt"]
    assert view.content_length() <= 4000
    assert view.total_children_count <= 40
    assert "[レベル復元用のコマンド]" in messages.details(plan.source, plan.target, plan.discord, plan.options)


@pytest.mark.asyncio
async def test_status_serializes_v2_and_attachment(world):
    """処理中の画面をtxt付きComponents V2として送信できる。"""
    # 非機能要件：Discord.pyが生成する送信データにV2フラグと添付参照が含まれる。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    view = MigrationStatusView(plan, 99, messages.PROCESSING)
    # When
    with handle_message_parameters(
        content=None,
        embed=None,
        attachments=[plan.detail_file()],
        view=view,
        allowed_mentions=discord.AllowedMentions.none(),
    ) as parameters:
        assert parameters.multipart is not None
        payload = json.loads(next(part["value"] for part in parameters.multipart if part["name"] == "payload_json"))
    # Then
    assert discord.MessageFlags._from_value(payload["flags"]).components_v2
    assert payload["content"] is None and payload["embeds"] == []
    assert payload["allowed_mentions"]["parse"] == []
    assert payload["attachments"][0]["filename"] == "account-migration.txt"
    assert payload["components"][-1]["file"]["url"] == "attachment://account-migration.txt"
