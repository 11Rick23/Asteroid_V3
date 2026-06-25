from __future__ import annotations

from typing import cast

import pytest
from discord import app_commands

from app.common.command_groups import (
    SETUP_GROUP_DESCRIPTION,
    SETUP_GROUP_NAME,
    get_or_create_setup_group,
    register_setup_command,
)
from app.core.bot import AsteroidBot
from tests.support.command_fakes import FakeCommandBot


async def _dummy_callback(_interaction):
    return None


def _command(name: str) -> app_commands.Command:
    return app_commands.Command(name=name, description=f"{name} command", callback=_dummy_callback)


def test_creates_setup_group():
    """setup group が未登録の場合は管理者向け guild-only group として作成する。"""
    # 機能要件：未登録の setup group は共有 group として作成される。
    # 非機能要件：setup group は guild 限定かつ管理者向け権限で公開される。
    # Given
    bot = FakeCommandBot()

    # When
    group = get_or_create_setup_group(cast(AsteroidBot, bot))

    # Then
    assert group.name == SETUP_GROUP_NAME
    assert group.description == SETUP_GROUP_DESCRIPTION
    assert bot.tree.get_command(SETUP_GROUP_NAME) is group
    assert group.guild_only is True
    assert group.default_permissions is not None
    assert group.default_permissions.administrator is True


def test_reuses_setup_group():
    """setup group が既に存在する場合は同じ group を再利用する。"""
    # 機能要件：既存の setup group がある場合は新規作成せず再利用する。
    # Given
    bot = FakeCommandBot()
    existing = get_or_create_setup_group(cast(AsteroidBot, bot))

    # When
    group = get_or_create_setup_group(cast(AsteroidBot, bot))

    # Then
    assert group is existing


def test_rejects_name_conflict():
    """setup 名が Group 以外で登録済みの場合は誤登録を防ぐため失敗する。"""
    # 非機能要件：setup group 名の衝突では誤った command 構造を作らず失敗する。
    # Given
    bot = FakeCommandBot()
    bot.tree.add_command(_command(SETUP_GROUP_NAME))

    # When / Then
    with pytest.raises(RuntimeError, match="Group ではありません"):
        get_or_create_setup_group(cast(AsteroidBot, bot))


def test_registers_setup_command_once():
    """setup command は shared setup group に一度だけ登録する。"""
    # 機能要件：setup command は共有 setup group の子 command として登録される。
    # 非機能要件：同じ setup command を重複登録しない。
    # Given
    bot = FakeCommandBot()
    command = _command("auth")

    # When
    register_setup_command(cast(AsteroidBot, bot), command)
    register_setup_command(cast(AsteroidBot, bot), command)

    # Then
    group = get_or_create_setup_group(cast(AsteroidBot, bot))
    assert group.get_command("auth") is command
    assert len(group.commands) == 1
