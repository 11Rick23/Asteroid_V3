from __future__ import annotations

from discord import app_commands

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
