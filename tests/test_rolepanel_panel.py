from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from app.core.bot import AsteroidBot
from app.features.rolepanel.panel import ROLE_PANEL_ID, ROLE_PANEL_OFFLINE_DESCRIPTION, RolePanel
from app.features.rolepanel.views import RolePanelView


class FakePanelManager:
    def __init__(self) -> None:
        self.registrations: list[tuple[str, int, object, str]] = []
        self.initialized: list[str] = []
        self.refreshed: list[str] = []
        self.unregistered: list[str] = []

    def register(self, panel_id: str, channel_id: int, render: object, *, offline_description: str) -> None:
        self.registrations.append((panel_id, channel_id, render, offline_description))

    async def initialize(self, panel_id: str) -> bool:
        self.initialized.append(panel_id)
        return True

    async def refresh(self, panel_id: str) -> bool:
        self.refreshed.append(panel_id)
        return True

    def unregister(self, panel_id: str) -> None:
        self.unregistered.append(panel_id)


class FakeRolePanelRepository:
    async def get_categories(self) -> list[object]:
        return []


def build_panel() -> tuple[RolePanel, FakePanelManager]:
    panels = FakePanelManager()
    guild = SimpleNamespace(id=100)
    bot = cast(
        AsteroidBot,
        SimpleNamespace(
            panels=panels,
            services={},
            config=SimpleNamespace(
                discord=SimpleNamespace(guild_id=100),
                rolepanel=SimpleNamespace(panel_channel_id=200),
            ),
            db=SimpleNamespace(role_panel=FakeRolePanelRepository()),
            get_guild=lambda guild_id: guild if guild_id == guild.id else None,
        ),
    )
    return RolePanel(bot), panels


@pytest.mark.asyncio
async def test_role_panel_registers_and_uses_common_manager() -> None:
    panel, panels = build_panel()

    assert panels.registrations == [(ROLE_PANEL_ID, 200, panel.render, ROLE_PANEL_OFFLINE_DESCRIPTION)]
    assert await panel.initialize() is True
    assert await panel.refresh() is True
    panel.unregister()

    assert panels.initialized == [ROLE_PANEL_ID]
    assert panels.refreshed == [ROLE_PANEL_ID]
    assert panels.unregistered == [ROLE_PANEL_ID]


@pytest.mark.asyncio
async def test_role_panel_renders_embed_and_persistent_view() -> None:
    panel, _ = build_panel()

    content = await panel.render()

    assert len(content.embeds) == 1
    assert content.embeds[0].title == "ロールパネル"
    assert content.embeds[0].fields[0].name == "カテゴリ未設定"
    assert isinstance(content.view, RolePanelView)
    assert content.view.timeout is None
