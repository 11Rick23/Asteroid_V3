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
    get_panel_marker_id,
)


class FakeMessage:
    def __init__(self, message_id: int, author_id: int, *, components: list[object] | None = None) -> None:
        self.id = message_id
        self.author = SimpleNamespace(id=author_id)
        self.components = components or []
        self.edits: list[dict[str, Any]] = []
        self.delete_count = 0

    async def edit(self, **kwargs: Any) -> None:
        self.edits.append(kwargs)
        view = kwargs.get("view")
        if isinstance(view, discord.ui.LayoutView):
            self.components = list(view.children)
        elif view is not None:
            self.components = []

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
        view = kwargs.get("view")
        if isinstance(view, discord.ui.LayoutView):
            message.components = list(view.children)
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


def marker_component(panel_id: str) -> SimpleNamespace:
    return SimpleNamespace(id=get_panel_marker_id(panel_id), components=[])


def get_layout_view_marker_id(payload: dict[str, Any]) -> int | None:
    view = cast(discord.ui.LayoutView, payload["view"])
    return view.children[0].id


@pytest.mark.asyncio
async def test_initialize_reuses_latest_message_when_panel_marker_matches() -> None:
    latest_message = FakeMessage(50, author_id=10, components=[marker_component("rolepanel")])
    channel = FakeChannel(20, bot_user_id=10, history_messages=[latest_message])
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot({20: channel})))
    manager.register("rolepanel", 20, render_components_v2_panel, offline_description="利用できません。")

    assert await manager.initialize("rolepanel") is True

    assert manager.get_message("rolepanel") is latest_message
    assert channel.sent_messages == []
    assert latest_message.edits[0]["embeds"] == []
    assert get_layout_view_marker_id(latest_message.edits[0]) == get_panel_marker_id("rolepanel")


@pytest.mark.asyncio
async def test_initialize_sends_new_message_when_latest_bot_message_has_no_panel_marker() -> None:
    latest_message = FakeMessage(50, author_id=10)
    channel = FakeChannel(20, bot_user_id=10, history_messages=[latest_message])
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot({20: channel})))
    manager.register("rolepanel", 20, render_components_v2_panel, offline_description="利用できません。")

    assert await manager.initialize("rolepanel") is True

    assert manager.get_message("rolepanel") is channel.sent_messages[0]
    assert latest_message.edits == []
    assert len(channel.sent_payloads) == 1
    assert get_layout_view_marker_id(channel.sent_payloads[0]) == get_panel_marker_id("rolepanel")


@pytest.mark.asyncio
async def test_initialize_sends_new_message_when_latest_bot_message_has_different_panel_marker() -> None:
    latest_message = FakeMessage(50, author_id=10, components=[marker_component("ranking")])
    channel = FakeChannel(20, bot_user_id=10, history_messages=[latest_message])
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot({20: channel})))
    manager.register("rolepanel", 20, render_components_v2_panel, offline_description="利用できません。")

    assert await manager.initialize("rolepanel") is True

    assert manager.get_message("rolepanel") is channel.sent_messages[0]
    assert latest_message.edits == []
    assert get_layout_view_marker_id(channel.sent_payloads[0]) == get_panel_marker_id("rolepanel")


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
    assert get_layout_view_marker_id(channel.sent_payloads[0]) == get_panel_marker_id("rolepanel")


@pytest.mark.asyncio
async def test_initialize_clears_legacy_content_when_switching_to_components_v2() -> None:
    latest_message = FakeMessage(50, author_id=10, components=[marker_component("rolepanel")])
    channel = FakeChannel(20, bot_user_id=10, history_messages=[latest_message])
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot({20: channel})))
    manager.register("rolepanel", 20, render_components_v2_panel, offline_description="利用できません。")

    assert await manager.initialize("rolepanel") is True

    assert latest_message.edits[0]["content"] is None
    assert latest_message.edits[0]["embeds"] == []
    assert latest_message.edits[0]["attachments"] == []
    assert isinstance(latest_message.edits[0]["view"], discord.ui.LayoutView)
    assert get_layout_view_marker_id(latest_message.edits[0]) == get_panel_marker_id("rolepanel")


@pytest.mark.asyncio
async def test_set_all_offline_updates_every_panel_with_components_v2() -> None:
    first_message = FakeMessage(50, author_id=10, components=[marker_component("ranking")])
    second_message = FakeMessage(60, author_id=10, components=[marker_component("rolepanel")])
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
    expected_panels = (
        (first_message, "ranking", "ランキングは現在確認できません。"),
        (second_message, "rolepanel", "ロールパネルは現在利用できません。"),
    )
    for message, panel_id, expected_description in expected_panels:
        edit = message.edits[0]
        text = get_layout_view_text(edit)
        assert edit["embeds"] == []
        assert edit["attachments"] == []
        assert get_layout_view_marker_id(edit) == get_panel_marker_id(panel_id)
        assert "# BOT は現在オフラインです" in text
        assert expected_description in text
        assert "**理由**\nメンテナンス" in text
        assert "**予定期間**\n1時間" in text
        assert "**緊急連絡先**\n<@10>" in text
        assert "**最終更新日時**" in text


@pytest.mark.asyncio
async def test_refresh_does_not_overwrite_offline_display() -> None:
    message = FakeMessage(50, author_id=10, components=[marker_component("auth")])
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
    message = FakeMessage(50, author_id=10, components=[marker_component("auth")])
    channel = FakeChannel(20, bot_user_id=10, history_messages=[message])
    manager = PersistentPanelManager(cast(PersistentPanelBot, FakeBot({20: channel})))
    manager.register("auth", 20, render_panel, offline_description="認証システムは現在利用できません。")

    await manager.set_all_offline(OfflineInfo(reason="メンテナンス", planned_period="1時間"))

    assert await manager.initialize("auth") is False
    assert len(message.edits) == 1
    assert "# BOT は現在オフラインです" in get_layout_view_text(message.edits[0])


@pytest.mark.asyncio
async def test_unregister_does_not_delete_panel_message() -> None:
    message = FakeMessage(50, author_id=10, components=[marker_component("free_category")])
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
    good_message = FakeMessage(60, author_id=10, components=[marker_component("rolepanel")])
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
