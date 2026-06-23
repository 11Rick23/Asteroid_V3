from __future__ import annotations

from typing import cast

import discord
import pytest

from app.common.offline import OfflineInfo
from app.common.persistent_panels import (
    PersistentPanelBot,
    PersistentPanelContent,
    PersistentPanelManager,
    get_panel_marker_id,
)
from tests.support.discord_fakes import FakePanelBot, FakePanelComponent, FakePanelMessage, FakeTextChannel


async def _render(title: str = "通常") -> PersistentPanelContent:
    return PersistentPanelContent(embeds=(discord.Embed(title=title),))


def test_rejects_duplicate():
    """同じ panel_id の二重登録は lifecycle の衝突を避けるため拒否する。"""
    # Given
    channel = FakeTextChannel(channel_id=10)
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakePanelBot(channel=channel)))
    manager.register("main", 10, _render, offline_description="停止中")

    # When / Then
    with pytest.raises(ValueError, match="既に登録"):
        manager.register("main", 10, _render, offline_description="停止中")


@pytest.mark.asyncio
async def test_reuses_latest_message():
    """初期化時は同じ panel marker を持つ最新 BOT メッセージを編集して再利用する。"""
    # Given
    marker = FakePanelComponent(id=get_panel_marker_id("main"))
    latest_message = FakePanelMessage(message_id=55, author_id=42, components=[marker])
    channel = FakeTextChannel(channel_id=10, latest_message=latest_message)
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakePanelBot(channel=channel, user_id=42)))
    manager.register("main", 10, _render, offline_description="停止中")

    # When
    result = await manager.initialize("main")

    # Then
    assert result is True
    assert manager.get_message("main") is latest_message
    assert channel.sent_messages == []
    assert latest_message.edits


@pytest.mark.asyncio
async def test_skips_after_offline():
    """オフライン化後の refresh は通常表示で上書きせず False を返す。"""
    # Given
    channel = FakeTextChannel(channel_id=10)
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakePanelBot(channel=channel, user_id=42)))
    manager.register("main", 10, _render, offline_description="停止中")
    await manager.initialize("main")
    message = manager.get_message("main")

    # When
    offline_results = await manager.set_all_offline(OfflineInfo(reason="停止", planned_period="未定"))
    refresh_result = await manager.refresh("main")

    # Then
    assert offline_results == {"main": True}
    assert refresh_result is False
    assert manager.get_message("main") is message


def test_marker_is_stable():
    """panel marker ID は同じ panel_id で安定し、Discord component ID として正の値になる。"""
    # Given / When
    first = get_panel_marker_id("main")
    second = get_panel_marker_id("main")

    # Then
    assert first == second
    assert first > 0
