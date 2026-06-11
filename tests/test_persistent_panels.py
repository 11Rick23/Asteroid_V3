from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from app.common.offline import OfflineInfo
from app.common.persistent_panels import (
    PersistentPanelBot,
    PersistentPanelContent,
    PersistentPanelManager,
)


class FakeMessage:
    def __init__(self, message_id: int, author_id: int) -> None:
        self.id = message_id
        self.author = SimpleNamespace(id=author_id)
        self.edits: list[dict[str, Any]] = []
        self.delete_count = 0

    async def edit(self, **kwargs: Any) -> None:
        self.edits.append(kwargs)

    async def delete(self) -> None:
        self.delete_count += 1


class FakeChannel:
    def __init__(self, channel_id: int, bot_user_id: int, history_messages: list[FakeMessage]) -> None:
        self.id = channel_id
        self.guild = SimpleNamespace(id=100)
        self.bot_user_id = bot_user_id
        self.history_messages = history_messages
        self.sent_messages: list[FakeMessage] = []
        self.sent_payloads: list[dict[str, Any]] = []

    def history(self, *, limit: int) -> Any:
        async def iterator() -> Any:
            for message in self.history_messages[:limit]:
                yield message

        return iterator()

    async def fetch_message(self, message_id: int) -> FakeMessage:
        raise AssertionError("fetch_message should not be called")

    async def send(self, **kwargs: Any) -> FakeMessage:
        message = FakeMessage(1000 + len(self.sent_messages), self.bot_user_id)
        self.sent_messages.append(message)
        self.sent_payloads.append(kwargs)
        return message


class FakeBot:
    def __init__(self, channels: dict[int, FakeChannel]) -> None:
        self.user = SimpleNamespace(id=10)
        self.channels = channels

    def get_channel(self, channel_id: int) -> FakeChannel | None:
        return self.channels.get(channel_id)

    async def fetch_channel(self, channel_id: int) -> FakeChannel:
        raise AssertionError("fetch_channel should not be called")

    def is_operating_channel(self, channel: object) -> bool:
        return getattr(getattr(channel, "guild", None), "id", None) == 100

    async def application_info(self) -> discord.AppInfo:
        return cast(
            discord.AppInfo,
            SimpleNamespace(
                owner=SimpleNamespace(mention="<@10>"),
                team=None,
            ),
        )


async def render_panel() -> PersistentPanelContent:
    return PersistentPanelContent(
        embeds=(discord.Embed(title="通常表示"),),
        view=discord.ui.View(timeout=None),
    )


@pytest.mark.asyncio
async def test_initialize_reuses_latest_message_when_authored_by_bot() -> None:
    latest_message = FakeMessage(50, author_id=10)
    channel = FakeChannel(20, bot_user_id=10, history_messages=[latest_message])
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot({20: channel})))
    manager.register("ranking", 20, render_panel)

    assert await manager.initialize("ranking") is True

    assert manager.get_message("ranking") is latest_message
    assert channel.sent_messages == []
    assert latest_message.edits[0]["embeds"][0].title == "通常表示"
    assert latest_message.edits[0]["view"] is not None


@pytest.mark.asyncio
async def test_initialize_sends_new_message_when_latest_message_is_not_authored_by_bot() -> None:
    channel = FakeChannel(20, bot_user_id=10, history_messages=[FakeMessage(50, author_id=99)])
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot({20: channel})))
    manager.register("rolepanel", 20, render_panel)

    assert await manager.initialize("rolepanel") is True

    assert manager.get_message("rolepanel") is channel.sent_messages[0]
    assert channel.sent_payloads[0]["embeds"][0].title == "通常表示"


@pytest.mark.asyncio
async def test_set_all_offline_updates_every_panel_and_removes_views() -> None:
    first_message = FakeMessage(50, author_id=10)
    second_message = FakeMessage(60, author_id=10)
    channels = {
        20: FakeChannel(20, bot_user_id=10, history_messages=[first_message]),
        30: FakeChannel(30, bot_user_id=10, history_messages=[second_message]),
    }
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot(channels)))
    manager.register("ranking", 20, render_panel)
    manager.register("rolepanel", 30, render_panel)

    results = await manager.set_all_offline(
        OfflineInfo(reason="メンテナンス", planned_period="1時間"),
    )

    assert results == {"ranking": True, "rolepanel": True}
    for message in (first_message, second_message):
        edit = message.edits[0]
        embed = edit["embeds"][0]
        assert embed.title == "BOT は現在オフラインです"
        assert embed.fields[0].value == "メンテナンス"
        assert embed.fields[1].value == "1時間"
        assert embed.fields[2].value == "<@10>"
        assert edit["view"] is None


@pytest.mark.asyncio
async def test_refresh_restores_normal_content_after_offline_display() -> None:
    message = FakeMessage(50, author_id=10)
    channel = FakeChannel(20, bot_user_id=10, history_messages=[message])
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot({20: channel})))
    manager.register("auth", 20, render_panel)

    assert await manager.initialize("auth") is True
    await manager.set_all_offline(OfflineInfo(reason="メンテナンス", planned_period="1時間"))
    assert await manager.refresh("auth") is True

    restored = message.edits[-1]
    assert restored["embeds"][0].title == "通常表示"
    assert restored["view"] is not None


@pytest.mark.asyncio
async def test_unregister_does_not_delete_panel_message() -> None:
    message = FakeMessage(50, author_id=10)
    channel = FakeChannel(20, bot_user_id=10, history_messages=[message])
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot({20: channel})))
    manager.register("free_category", 20, render_panel)

    assert await manager.initialize("free_category") is True
    manager.unregister("free_category")

    assert message.delete_count == 0


@pytest.mark.asyncio
async def test_set_all_offline_continues_after_panel_failure() -> None:
    good_message = FakeMessage(60, author_id=10)
    channels = {
        30: FakeChannel(30, bot_user_id=10, history_messages=[good_message]),
    }
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot(channels)))
    manager.register("missing", 20, render_panel)
    manager.register("rolepanel", 30, render_panel)

    results = await manager.set_all_offline(
        OfflineInfo(reason="メンテナンス", planned_period="1時間"),
    )

    assert results == {"missing": False, "rolepanel": True}
    assert good_message.edits[0]["embeds"][0].title == "BOT は現在オフラインです"
