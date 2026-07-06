from __future__ import annotations

from discord import app_commands

from app.features.rolepanel.commands import rolepanel_group


def test_group_is_admin_only():
    """ロールパネル管理 group は guild 限定で管理者権限をデフォルト権限にする。"""
    # 非機能要件：ロールパネル管理 group は guild 限定かつ管理者向け権限で公開される。
    # Given / When / Then
    assert rolepanel_group.name == "rolepanel"
    assert rolepanel_group.guild_only is True
    assert rolepanel_group.default_permissions is not None
    assert rolepanel_group.default_permissions.administrator is True


def test_require_boost_arguments_are_japanese():
    """ブースター限定設定 command の公開引数名は日本語で登録する。"""
    # 機能要件：ブースター限定設定 command はカテゴリと有効/無効を日本語引数として公開する。
    # Given
    command = rolepanel_group.get_command("require_boost")

    # When / Then
    assert isinstance(command, app_commands.Command)
    assert [parameter.display_name for parameter in command.parameters] == ["カテゴリ", "ブースター限定"]
