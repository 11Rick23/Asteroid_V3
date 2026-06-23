from __future__ import annotations

from typing import cast

from discord import app_commands

from app.features.suggest.cog import suggest_group


def test_group_is_admin_only():
    """suggestion group は guild 限定で管理者権限をデフォルト権限にする。"""
    # Given / When / Then
    assert suggest_group.name == "suggestion"
    assert suggest_group.guild_only is True
    assert suggest_group.default_permissions is not None
    assert suggest_group.default_permissions.administrator is True


def test_reason_is_japanese():
    """approve / deny の公開引数名と説明は日本語で登録する。"""
    # Given
    approve = suggest_group.get_command("approve")
    deny = suggest_group.get_command("deny")

    # When / Then
    assert approve is not None
    assert deny is not None
    approve_command = cast(app_commands.Command, approve)
    deny_command = cast(app_commands.Command, deny)
    assert approve_command.parameters[0].display_name == "理由"
    assert approve_command.parameters[0].description == "要望を可決する理由"
    assert deny_command.parameters[0].display_name == "理由"
    assert deny_command.parameters[0].description == "要望を否決する理由"
