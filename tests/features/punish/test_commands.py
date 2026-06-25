from __future__ import annotations

from discord import app_commands

from app.features.punish.cog import punish_group


def test_group_is_admin_only():
    """処罰 command group は guild 限定で管理者権限をデフォルト権限にする。"""
    # 非機能要件：処罰 command group は guild 限定かつ管理者向け権限で公開される。
    # Given / When / Then
    assert punish_group.name == "punish"
    assert punish_group.guild_only is True
    assert punish_group.default_permissions is not None
    assert punish_group.default_permissions.administrator is True


def test_timeout_arguments_are_japanese():
    """timeout command の公開引数名は日本語で登録する。"""
    # 機能要件：timeout command は対象、期間、理由、執行猶予を日本語引数として公開する。
    # Given
    command = punish_group.get_command("timeout")

    # When / Then
    assert isinstance(command, app_commands.Command)
    assert [parameter.display_name for parameter in command.parameters] == [
        "対象ユーザー",
        "期間",
        "理由",
        "執行猶予",
    ]
