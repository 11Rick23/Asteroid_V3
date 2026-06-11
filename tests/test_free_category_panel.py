from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from app.core.bot import AsteroidBot
from app.features.free_category.panel import (
    FREE_CATEGORY_OFFLINE_DESCRIPTION,
    FREE_CATEGORY_PANEL_ID,
    FreeCategoryPanel,
)
from app.features.free_category.views import CreateChannelButtonView


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
async def test_free_category_panel_renders_embed_and_persistent_view() -> None:
    panel, _ = build_panel()

    content = await panel.render()

    assert len(content.embeds) == 1
    assert content.embeds[0].title == "フリーカテゴリー内に新しいフリーチャンネルの作成"
    assert isinstance(content.view, CreateChannelButtonView)
    assert content.view.timeout is None
