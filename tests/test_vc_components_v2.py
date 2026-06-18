from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from app.core.bot import AsteroidBot
from app.features.vc.service import VoiceCreateService
from app.features.vc.views import ChangeNameButton, TogglePrivacyButton, VoiceControlView


class FakeBot:
    def __init__(self) -> None:
        self.config = SimpleNamespace(vc=SimpleNamespace(voice_create_channel_id=999))
        self.messages: dict[int, FakeMessage] = {}
        self.remembered_messages: list[FakeMessage] = []

    def remember_message(self, message: FakeMessage) -> None:
        self.remembered_messages.append(message)
        self.messages[message.id] = message

    def get_message(self, message_id: int) -> FakeMessage | None:
        return self.messages.get(message_id)


class FakeGuild:
    def __init__(self) -> None:
        self.id = 200
        self.default_role = object()


class FakeVoiceChannel:
    def __init__(self) -> None:
        self.id = 100
        self.name = "作業VC"
        self.user_limit = 3
        self.guild = FakeGuild()
        self.overwrites: dict[object, discord.PermissionOverwrite] = {}
        self.sent_payloads: list[dict[str, Any]] = []

    def overwrites_for(self, _: object) -> discord.PermissionOverwrite:
        return discord.PermissionOverwrite(view_channel=True, connect=True)

    async def send(self, **kwargs: Any) -> FakeMessage:
        self.sent_payloads.append(kwargs)
        return FakeMessage(500)


class FakeMember:
    id = 10
    mention = "<@10>"
    color = discord.Color.green()


class FakeMessage:
    def __init__(self, message_id: int) -> None:
        self.id = message_id
        self.embeds: list[discord.Embed] = []
        self.edit_calls: list[dict[str, Any]] = []

    async def edit(self, **kwargs: Any) -> None:
        self.edit_calls.append(kwargs)


def text_contents(view: discord.ui.LayoutView) -> str:
    return "\n".join(child.content for child in view.walk_children() if isinstance(child, discord.ui.TextDisplay))


def find_text_index(container: discord.ui.Container, prefix: str) -> int:
    for index, child in enumerate(container.children):
        if isinstance(child, discord.ui.TextDisplay) and child.content.startswith(prefix):
            return index
    raise AssertionError(f"{prefix} が見つかりません")


def test_voice_control_view_renders_components_v2_layout() -> None:
    service = VoiceCreateService(cast(AsteroidBot, FakeBot()))
    channel = cast(discord.VoiceChannel, FakeVoiceChannel())

    view = VoiceControlView(service, channel, color=discord.Color.blue())
    content = text_contents(view)

    assert view.timeout is None
    assert view.has_components_v2()
    assert "# 作業VC" in content
    assert "### 人数制限" in content
    assert "### ブロックしたユーザー" in content
    assert "### 管理権限を与えたユーザー" in content
    assert "### VC名" not in content
    assert "### 公開設定" not in content
    assert "現在の" not in content
    assert "なし" not in content


def test_voice_control_buttons_are_directly_below_channel_title() -> None:
    service = VoiceCreateService(cast(AsteroidBot, FakeBot()))
    channel = cast(discord.VoiceChannel, FakeVoiceChannel())

    view = VoiceControlView(service, channel)
    container = cast(discord.ui.Container, view.children[0])
    title = cast(discord.ui.TextDisplay, container.children[0])
    row = cast(discord.ui.ActionRow[VoiceControlView], container.children[1])
    change_name_button = row.children[0]
    toggle_privacy_button = row.children[1]

    assert title.content == "# 作業VC"
    assert isinstance(change_name_button, ChangeNameButton)
    assert change_name_button.custom_id == "vc_change_name_button"
    assert change_name_button.label == "VC名を変更"
    assert isinstance(toggle_privacy_button, TogglePrivacyButton)
    assert toggle_privacy_button.custom_id == "vc_toggle_private_button"
    assert toggle_privacy_button.label == "非公開にする"


def test_voice_control_selects_are_placed_below_related_text() -> None:
    service = VoiceCreateService(cast(AsteroidBot, FakeBot()))
    channel = cast(discord.VoiceChannel, FakeVoiceChannel())

    view = VoiceControlView(service, channel)
    container = cast(discord.ui.Container, view.children[0])

    limit_row = cast(
        discord.ui.ActionRow[VoiceControlView],
        container.children[find_text_index(container, "### 人数制限") + 1],
    )
    block_row = cast(
        discord.ui.ActionRow[VoiceControlView],
        container.children[find_text_index(container, "### ブロックしたユーザー") + 1],
    )
    op_row = cast(
        discord.ui.ActionRow[VoiceControlView],
        container.children[find_text_index(container, "### 管理権限を与えたユーザー") + 1],
    )

    assert isinstance(limit_row.children[0], discord.ui.Select)
    assert limit_row.children[0].custom_id == "vc_user_limit_select"
    assert next(option for option in limit_row.children[0].options if option.value == "3").default is True
    assert isinstance(block_row.children[0], discord.ui.UserSelect)
    assert block_row.children[0].custom_id == "vc_block_user_select"
    assert isinstance(op_row.children[0], discord.ui.UserSelect)
    assert op_row.children[0].custom_id == "vc_op_user_select"


@pytest.mark.asyncio
async def test_send_control_message_sends_creation_mention_once_before_components_v2_view() -> None:
    bot = FakeBot()
    service = VoiceCreateService(cast(AsteroidBot, bot))
    channel = FakeVoiceChannel()

    await service.send_control_message(
        cast(discord.VoiceChannel, channel),
        cast(discord.Member, FakeMember()),
        mention_member=True,
    )

    assert len(channel.sent_payloads) == 2
    assert channel.sent_payloads[0] == {"content": "<@10>"}
    assert set(channel.sent_payloads[1]) == {"view"}
    view = channel.sent_payloads[1]["view"]
    assert isinstance(view, discord.ui.LayoutView)
    assert view.has_components_v2()
    assert "<@10>" not in text_contents(view)
    assert bot.remembered_messages == [bot.messages[500]]


@pytest.mark.asyncio
async def test_refresh_control_panels_clears_legacy_payload_when_editing_to_v2() -> None:
    bot = FakeBot()
    message = FakeMessage(500)
    bot.messages[500] = message
    service = VoiceCreateService(cast(AsteroidBot, bot))
    channel = cast(discord.VoiceChannel, FakeVoiceChannel())
    service.control_panel_messages[100] = (500, 0x123456)

    await service.refresh_control_panels(channel)

    assert len(message.edit_calls) == 1
    edit_call = message.edit_calls[0]
    assert edit_call["content"] is None
    assert edit_call["embeds"] == []
    assert edit_call["attachments"] == []
    view = edit_call["view"]
    assert isinstance(view, discord.ui.LayoutView)
    assert view.has_components_v2()

