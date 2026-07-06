from __future__ import annotations

from discord import app_commands

from app.features.vc.cog import vc_group


def test_commands_are_guild_only():
    """VC 操作コマンドは guild 内 VC の状態変更として登録する。"""
    # 非機能要件：VC 操作 command は guild 限定で公開される。
    # Given / When
    commands = vc_group.commands

    # Then
    assert commands
    assert all(command.guild_only for command in commands)


def test_name_argument_is_japanese():
    """VC 名変更 command の公開引数名は日本語で登録する。"""
    # 機能要件：VC 名変更 command は新しい VC 名を日本語引数として公開する。
    # Given
    command = vc_group.get_command("name")

    # When / Then
    assert isinstance(command, app_commands.Command)
    assert [parameter.display_name for parameter in command.parameters] == ["vc名"]
