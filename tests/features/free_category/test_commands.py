from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest
from discord import app_commands

from app.features.free_category import cog, messages
from app.features.free_category.cog import free_category_group


def test_commands_are_guild_only():
    """フリーカテゴリー操作コマンドは guild 内チャンネルの状態変更として登録する。"""
    # 非機能要件：フリーカテゴリーの状態変更 command は guild 限定で公開される。
    # Given / When
    commands = free_category_group.commands

    # Then
    assert commands
    assert all(command.guild_only for command in commands)


def test_edit_arguments_are_japanese():
    """チャンネル編集 command の公開引数名は日本語で登録する。"""
    # 機能要件：フリーチャンネル編集 command はチャンネル名とトピックを日本語引数として公開する。
    # Given
    command = free_category_group.get_command("edit")

    # When / Then
    assert isinstance(command, app_commands.Command)
    assert [parameter.display_name for parameter in command.parameters] == ["チャンネル名", "トピック"]


def test_edit_length_limits():
    """編集引数の文字数上限と説明を Discord に公開する。"""
    # 機能要件：名前は100文字、トピックは500文字まで入力できる。
    # Given / When
    parameters = {parameter.name: parameter for parameter in cog.edit.parameters}

    # Then
    assert (parameters["name"].min_value, parameters["name"].max_value) == (1, 100)
    assert (parameters["topic"].min_value, parameters["topic"].max_value) == (1, 500)
    assert "100文字" in parameters["name"].description
    assert "500文字" in parameters["topic"].description


@pytest.fixture
def edit_context(monkeypatch):
    channel = SimpleNamespace(
        id=2, guild=SimpleNamespace(id=1), name="旧チャンネル", topic="旧" * 1024, edit=AsyncMock()
    )
    service = SimpleNamespace(
        ensure_manageable_text_channel=AsyncMock(return_value=channel),
        get_edit_cooldown_retry_after=Mock(return_value=0),
        start_edit_cooldown=Mock(),
    )
    interaction = SimpleNamespace(
        client=SimpleNamespace(),
        user=SimpleNamespace(id=3, name="管理者"),
        response=SimpleNamespace(send_message=AsyncMock(), defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )
    monkeypatch.setattr(cog, "get_free_category_service", lambda _: service)
    return interaction, channel, service


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "topic"), [("a" * 101, None), (None, "b" * 501), ("", None), (None, "")])
async def test_rejects_long_edit(edit_context, name, topic):
    """空文字と上限を超える入力ではチャンネル変更やクールダウンを開始しない。"""
    # 非機能要件：不正入力による変更とクールダウン消費を防ぐ。
    # Given
    interaction, channel, service = edit_context

    # When
    await cast(Any, cog.edit.callback)(interaction, name=name, topic=topic)

    # Then
    channel.edit.assert_not_awaited()
    service.start_edit_cooldown.assert_not_called()
    interaction.response.defer.assert_not_awaited()
    interaction.response.send_message.assert_awaited_once_with(messages.EDIT_LENGTH_INVALID, ephemeral=True)


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "topic"), [("a" * 100, "b" * 500), (None, "b" * 500), ("a" * 100, None)])
async def test_edits_at_length_limit(edit_context, name, topic):
    """上限ちょうどの編集は保存でき、既存の長いトピックがあっても完了通知が上限内に収まる。"""
    # 機能要件：有効な名前とトピックは省略せずチャンネルに保存する。
    # 非機能要件：変更前の長いトピックで Embed の上限を超えない。
    # Given
    interaction, channel, _ = edit_context

    # When
    await cast(Any, cog.edit.callback)(interaction, name=name, topic=topic)

    # Then
    channel.edit.assert_awaited_once()
    if name is not None:
        assert channel.edit.call_args.kwargs["name"] == name
    if topic is not None:
        assert channel.edit.call_args.kwargs["topic"] == topic
    interaction.followup.send.assert_awaited_once()
    embed = interaction.followup.send.call_args.kwargs["embed"]
    assert all(len(field.value) <= 1024 for field in embed.fields)
    assert len(embed.description or "") <= 4096
    if topic is not None:
        rendered = embed.description if name is None else embed.fields[1].value
        assert "旧" * 499 + "…" in rendered
        assert topic in rendered
