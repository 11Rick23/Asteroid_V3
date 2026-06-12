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


async def render_components_v2_panel() -> PersistentPanelContent:
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(discord.ui.TextDisplay("# Components V2"))
    return PersistentPanelContent(embeds=(), view=view)


def get_layout_view_text(payload: dict[str, Any]) -> str:
    view = cast(discord.ui.LayoutView, payload["view"])
    container = cast(discord.ui.Container, view.children[0])
    return cast(discord.ui.TextDisplay, container.children[0]).content


@pytest.mark.asyncio
async def test_initialize_reuses_latest_message_when_authored_by_bot() -> None:
    latest_message = FakeMessage(50, author_id=10)
    channel = FakeChannel(20, bot_user_id=10, history_messages=[latest_message])
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot({20: channel})))
    manager.register("ranking", 20, render_panel, offline_description="ランキングは現在確認できません。")

    assert await manager.initialize("ranking") is True

    assert manager.get_message("ranking") is latest_message
    assert channel.sent_messages == []
    assert latest_message.edits[0]["embeds"][0].title == "通常表示"
    assert latest_message.edits[0]["view"] is not None


@pytest.mark.asyncio
async def test_initialize_sends_new_message_when_latest_message_is_not_authored_by_bot() -> None:
    channel = FakeChannel(20, bot_user_id=10, history_messages=[FakeMessage(50, author_id=99)])
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot({20: channel})))
    manager.register("rolepanel", 20, render_panel, offline_description="ロールパネルは現在利用できません。")

    assert await manager.initialize("rolepanel") is True

    assert manager.get_message("rolepanel") is channel.sent_messages[0]
    assert channel.sent_payloads[0]["embeds"][0].title == "通常表示"


@pytest.mark.asyncio
async def test_initialize_sends_components_v2_panel_without_embeds() -> None:
    channel = FakeChannel(20, bot_user_id=10, history_messages=[])
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot({20: channel})))
    manager.register("rolepanel", 20, render_components_v2_panel, offline_description="利用できません。")

    assert await manager.initialize("rolepanel") is True

    assert len(channel.sent_payloads) == 1
    assert "embeds" not in channel.sent_payloads[0]
    assert isinstance(channel.sent_payloads[0]["view"], discord.ui.LayoutView)


@pytest.mark.asyncio
async def test_initialize_clears_legacy_content_when_switching_to_components_v2() -> None:
    latest_message = FakeMessage(50, author_id=10)
    channel = FakeChannel(20, bot_user_id=10, history_messages=[latest_message])
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot({20: channel})))
    manager.register("rolepanel", 20, render_components_v2_panel, offline_description="利用できません。")

    assert await manager.initialize("rolepanel") is True

    assert latest_message.edits[0]["content"] is None
    assert latest_message.edits[0]["embeds"] == []
    assert latest_message.edits[0]["attachments"] == []
    assert isinstance(latest_message.edits[0]["view"], discord.ui.LayoutView)


@pytest.mark.asyncio
async def test_set_all_offline_updates_every_panel_with_components_v2() -> None:
    first_message = FakeMessage(50, author_id=10)
    second_message = FakeMessage(60, author_id=10)
    channels = {
        20: FakeChannel(20, bot_user_id=10, history_messages=[first_message]),
        30: FakeChannel(30, bot_user_id=10, history_messages=[second_message]),
    }
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot(channels)))
    manager.register("ranking", 20, render_panel, offline_description="ランキングは現在確認できません。")
    manager.register("rolepanel", 30, render_panel, offline_description="ロールパネルは現在利用できません。")

    results = await manager.set_all_offline(
        OfflineInfo(reason="メンテナンス", planned_period="1時間"),
    )

    assert results == {"ranking": True, "rolepanel": True}
    expected_descriptions = ("ランキングは現在確認できません。", "ロールパネルは現在利用できません。")
    for message, expected_description in zip((first_message, second_message), expected_descriptions, strict=True):
        edit = message.edits[0]
        text = get_layout_view_text(edit)
        assert edit["embeds"] == []
        assert edit["attachments"] == []
        assert "# BOT は現在オフラインです" in text
        assert expected_description in text
        assert "**理由**\nメンテナンス" in text
        assert "**予定期間**\n1時間" in text
        assert "**緊急連絡先**\n<@10>" in text
        assert "**最終更新日時**" in text


@pytest.mark.asyncio
async def test_refresh_does_not_overwrite_offline_display() -> None:
    message = FakeMessage(50, author_id=10)
    channel = FakeChannel(20, bot_user_id=10, history_messages=[message])
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot({20: channel})))
    manager.register("auth", 20, render_panel, offline_description="認証システムは現在利用できません。")

    assert await manager.initialize("auth") is True
    await manager.set_all_offline(OfflineInfo(reason="メンテナンス", planned_period="1時間"))
    assert await manager.refresh("auth") is False

    assert len(message.edits) == 2
    assert "# BOT は現在オフラインです" in get_layout_view_text(message.edits[-1])


@pytest.mark.asyncio
async def test_initialize_does_not_overwrite_offline_display() -> None:
    message = FakeMessage(50, author_id=10)
    channel = FakeChannel(20, bot_user_id=10, history_messages=[message])
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot({20: channel})))
    manager.register("auth", 20, render_panel, offline_description="認証システムは現在利用できません。")

    await manager.set_all_offline(OfflineInfo(reason="メンテナンス", planned_period="1時間"))

    assert await manager.initialize("auth") is False
    assert len(message.edits) == 1
    assert "# BOT は現在オフラインです" in get_layout_view_text(message.edits[0])


@pytest.mark.asyncio
async def test_unregister_does_not_delete_panel_message() -> None:
    message = FakeMessage(50, author_id=10)
    channel = FakeChannel(20, bot_user_id=10, history_messages=[message])
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot({20: channel})))
    manager.register(
        "free_category",
        20,
        render_panel,
        offline_description="フリーチャンネル作成機能は現在利用できません。",
    )

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
    manager.register("missing", 20, render_panel, offline_description="利用できません。")
    manager.register("rolepanel", 30, render_panel, offline_description="ロールパネルは現在利用できません。")

    results = await manager.set_all_offline(
        OfflineInfo(reason="メンテナンス", planned_period="1時間"),
    )

    assert results == {"missing": False, "rolepanel": True}
    assert "# BOT は現在オフラインです" in get_layout_view_text(good_message.edits[0])
