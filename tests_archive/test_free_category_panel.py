from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

import discord
import pytest

from app.core.bot import AsteroidBot
from app.features.free_category.panel import (
    FREE_CATEGORY_OFFLINE_DESCRIPTION,
    FREE_CATEGORY_PANEL_ID,
    FreeCategoryPanel,
)
from app.features.free_category.views import (
    CreateChannelButtonView,
    CreatedChannelView,
)


class FakePanelManager:
    def __init__(self) -> None:
        self.registrations: list[tuple[str, int, object, str]] = []
        self.initialized: list[str] = []
        self.unregistered: list[str] = []

    def register(self, panel_id: str, channel_id: int, render: object, *, offline_description: str) -> None:
        self.registrations.append((panel_id, channel_id, render, offline_description))

    async def initialize(self, panel_id: str) -> bool:
        self.initialized.append(panel_id)
        return True

    def unregister(self, panel_id: str) -> None:
        self.unregistered.append(panel_id)


def build_panel() -> tuple[FreeCategoryPanel, FakePanelManager]:
    panels = FakePanelManager()
    bot = cast(
        AsteroidBot,
        SimpleNamespace(
            panels=panels,
            services={},
            config=SimpleNamespace(
                free_category=SimpleNamespace(
                    text_create_channel_id=200,
                    text_create_channel_cooldown_seconds=86400,
                )
            ),
        ),
    )
    return FreeCategoryPanel(bot), panels


@pytest.mark.asyncio
async def test_free_category_panel_registers_and_uses_common_manager() -> None:
    panel, panels = build_panel()

    assert panels.registrations == [(FREE_CATEGORY_PANEL_ID, 200, panel.render, FREE_CATEGORY_OFFLINE_DESCRIPTION)]
    assert await panel.initialize() is True
    panel.unregister()

    assert panels.initialized == [FREE_CATEGORY_PANEL_ID]
    assert panels.unregistered == [FREE_CATEGORY_PANEL_ID]


@pytest.mark.asyncio
async def test_free_category_panel_renders_components_v2_container_and_persistent_button() -> None:
    panel, _ = build_panel()

    content = await panel.render()

    assert content.embeds == ()
    assert isinstance(content.view, CreateChannelButtonView)
    assert content.view.timeout is None
    assert content.view.has_components_v2()

    container = cast(discord.ui.Container, content.view.children[0])
    text = cast(discord.ui.TextDisplay, container.children[0])
    row = cast(discord.ui.ActionRow, container.children[1])
    button = cast(discord.ui.Button, row.children[0])

    assert container.accent_color is not None
    assert text.content == "# 新しいフリーチャンネルの作成"
    assert button.label == "チャンネルを作成"
    assert button.custom_id == "fc_create_channel_button"


def test_created_channel_view_renders_components_v2_container() -> None:
    creator = cast(
        discord.Member,
        SimpleNamespace(
            mention="<@100>",
            display_name="テストユーザー",
            display_avatar=SimpleNamespace(url="https://example.com/avatar.png"),
            color=discord.Color.green(),
        ),
    )
    channel = cast(discord.TextChannel, SimpleNamespace(mention="<#200>"))

    view = CreatedChannelView(
        creator,
        channel,
        created_at=datetime.fromtimestamp(1234567890, UTC),
    )

    assert view.timeout is None
    assert view.has_components_v2()

    container = cast(discord.ui.Container, view.children[0])
    section = cast(discord.ui.Section, container.children[0])
    text = cast(discord.ui.TextDisplay, section.children[0])
    thumbnail = cast(discord.ui.Thumbnail, section.accessory)

    assert container.accent_color == discord.Color.green()
    assert "# 新たなチャンネルが誕生しました…！" in text.content
    assert "作成日時 : <t:1234567890:F>" in text.content
    assert thumbnail.media.url == "https://example.com/avatar.png"
    assert "<@100> のフリーチャンネルです。" in text.content
    assert "チャンネルを盛り上げよう！" in text.content
