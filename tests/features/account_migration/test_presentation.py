from __future__ import annotations

from dataclasses import replace

import pytest

from app.database.account_migration import MigrationOptions
from app.features.account_migration import messages
from app.features.account_migration.presentation import preview_embed


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
async def test_embed_groups_fields_and_bounds_exclusions(world):
    """確認画面は数量・誕生日・権限を別欄にし、大量の除外ロールでも表示上限内に収める。"""
    # 機能要件：数量を横並びで比較でき、除外の全件はtxtで確認できる。
    # 非機能要件：DiscordのEmbed文字数制限を超えない。
    # Given
    plan = await world.service.preview(world.guild, world.source, 2, MigrationOptions())
    ids = tuple(range(100000000000000001, 100000000000000251))
    plan = replace(plan, discord=replace(plan.discord, skipped_roles=ids))
    # When
    embed = preview_embed(plan)
    content = messages.details(plan.source, plan.target, plan.discord, plan.options)
    # Then
    assert embed.description and "<@1>" in embed.description and "<@2>" in embed.description
    assert embed.fields[0].name == "💎 シャード"
    assert embed.fields[0].inline is True
    assert embed.fields[1].name == "⚡ パワー"
    assert embed.fields[1].inline is True
    excluded = next(field for field in embed.fields if field.name and field.name.startswith("⏭️"))
    assert excluded.value is not None
    assert excluded.value.count("<@&") == 5
    assert "ほか245件" in excluded.value
    assert f"ID: {ids[-1]}" in content
    assert len(embed) <= 6000
    for field in embed.fields:
        assert field.name is not None and field.value is not None
        assert len(field.name) <= 256 and len(field.value) <= 1024


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
    record = world.record.edit.call_args.kwargs["content"]
    assert "<@1> → <@2>" in record
    assert "実行者: <@99>" in record
    assert record.count("```\n") == 4
    assert len(record) < 2000
