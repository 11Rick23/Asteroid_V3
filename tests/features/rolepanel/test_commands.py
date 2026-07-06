from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest
from discord import app_commands

from app.database.repositories.role_panel import RolePanelCategoryDetail
from app.features.rolepanel.commands import rolepanel_group
from tests.support.discord_fakes import FakeInteraction, FakeUser


def _category(
    *,
    category_id: int,
    name: str,
    description: str | None,
    display_order: int,
) -> RolePanelCategoryDetail:
    now = datetime(2026, 6, 23)
    return RolePanelCategoryDetail(
        category_id=category_id,
        name=name,
        description=description,
        display_order=display_order,
        requires_boost=False,
        created_at=now,
        updated_at=now,
    )


class FakeRolePanelRepository:
    def __init__(self, categories: list[RolePanelCategoryDetail]) -> None:
        self.categories = categories

    async def get_categories(self) -> list[RolePanelCategoryDetail]:
        return self.categories


class FakeBot:
    def __init__(self, categories: list[RolePanelCategoryDetail]) -> None:
        self.services: dict[str, object] = {}
        self.db = SimpleNamespace(role_panel=FakeRolePanelRepository(categories))


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


@pytest.mark.asyncio
async def test_list_shows_category_settings():
    """rolepanel list はカテゴリ設定一覧を ephemeral で返す。"""
    # 機能要件：rolepanel list はカテゴリ名、説明文、表示順の一覧を返す。
    # 非機能要件：管理用一覧は ephemeral response として返す。
    # Given
    command = rolepanel_group.get_command("list")
    assert isinstance(command, app_commands.Command)
    interaction = FakeInteraction(
        client=FakeBot(
            [
                _category(category_id=1, name="通知", description="通知用です。", display_order=10),
                _category(category_id=2, name="イベント", description=None, display_order=20),
            ]
        ),
        guild_id=12345,
        user=FakeUser(100),
        channel_id=67890,
    )

    # When
    callback = cast(Callable[[Any], Awaitable[None]], command.callback)
    await callback(interaction)

    # Then
    assert interaction.response.sent_messages[0]["ephemeral"] is True
    embeds = interaction.response.sent_messages[0]["embeds"]
    assert len(embeds) == 1
    assert embeds[0].title == "ロールパネルカテゴリ設定一覧"
    assert [field.name for field in embeds[0].fields] == ["通知", "イベント"]
    assert embeds[0].fields[0].value == "表示順: `10`\n説明文:\n通知用です。"
