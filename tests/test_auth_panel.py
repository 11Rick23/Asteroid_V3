from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from app.core.bot import AsteroidBot
from app.features.auth.panel import AUTH_OFFLINE_DESCRIPTION, AUTH_PANEL_ID, AuthPanel
from app.features.auth.views import AuthButton


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


def build_panel() -> tuple[AuthPanel, FakePanelManager]:
    panels = FakePanelManager()
    bot = cast(
        AsteroidBot,
        SimpleNamespace(
            panels=panels,
            config=SimpleNamespace(auth=SimpleNamespace(panel_channel_id=200)),
        ),
    )
    return AuthPanel(bot), panels


@pytest.mark.asyncio
async def test_auth_panel_registers_and_uses_common_manager() -> None:
    panel, panels = build_panel()

    assert panels.registrations == [(AUTH_PANEL_ID, 200, panel.render, AUTH_OFFLINE_DESCRIPTION)]
    assert await panel.initialize() is True
    panel.unregister()

    assert panels.initialized == [AUTH_PANEL_ID]
    assert panels.unregistered == [AUTH_PANEL_ID]


@pytest.mark.asyncio
async def test_auth_panel_renders_embed_and_persistent_view() -> None:
    panel, _ = build_panel()

    content = await panel.render()

    assert len(content.embeds) == 1
    assert content.embeds[0].title == "下のボタンを押して認証してください！"
    assert isinstance(content.view, AuthButton)
    assert content.view.timeout is None
