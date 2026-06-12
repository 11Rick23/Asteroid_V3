from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from app.core.bot import AsteroidBot
from app.features.auth import views as auth_views
from app.features.auth.panel import AUTH_OFFLINE_DESCRIPTION, AUTH_PANEL_ID, AuthPanel
from app.features.auth.views import AuthButton, AuthChallengeView


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


class FakeResponse:
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.edits: list[dict[str, Any]] = []
        self.defers = 0

    async def send_message(self, **kwargs: Any) -> None:
        self.messages.append(kwargs)

    async def edit_message(self, **kwargs: Any) -> None:
        self.edits.append(kwargs)

    async def defer(self) -> None:
        self.defers += 1


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
async def test_auth_panel_renders_components_v2_container_and_persistent_button() -> None:
    panel, _ = build_panel()

    content = await panel.render()

    assert content.embeds == ()
    assert isinstance(content.view, AuthButton)
    assert content.view.timeout is None
    assert content.view.has_components_v2()

    container = cast(discord.ui.Container, content.view.children[0])
    text = cast(discord.ui.TextDisplay, container.children[0])
    row = cast(discord.ui.ActionRow, container.children[1])
    button = cast(discord.ui.Button, row.children[0])

    assert container.accent_color is not None
    assert "# サーバーへようこそ！" in text.content
    assert "チャットを開始する前に" in text.content
    assert button.label == "認証"
    assert button.custom_id == "auth_button"


def test_auth_challenge_renders_captcha_in_components_v2_container() -> None:
    bot = cast(AsteroidBot, SimpleNamespace())

    view = AuthChallengeView(bot, "12345", owner_id=100)

    assert view.has_components_v2()
    assert view.timeout == 300

    container = cast(discord.ui.Container, view.children[0])
    text = cast(discord.ui.TextDisplay, container.children[0])
    gallery = cast(discord.ui.MediaGallery, container.children[1])
    first_digit_row = cast(discord.ui.ActionRow, container.children[2])
    second_digit_row = cast(discord.ui.ActionRow, container.children[3])
    operation_row = cast(discord.ui.ActionRow, container.children[4])

    assert "# BOT検証を行います" in text.content
    assert "## **入力:** `未入力`" in text.content
    assert len(gallery.items) == 1
    assert gallery.items[0].media.url == "attachment://captcha.png"
    assert [cast(discord.ui.Button, button).label for button in first_digit_row.children] == [
        "1",
        "2",
        "3",
        "4",
        "5",
    ]
    assert [cast(discord.ui.Button, button).label for button in second_digit_row.children] == [
        "6",
        "7",
        "8",
        "9",
        "0",
    ]
    assert [cast(discord.ui.Button, button).label for button in operation_row.children] == [
        "1文字消す",
        "クリア",
        "検証",
    ]


def find_button(view: AuthChallengeView, custom_id: str) -> discord.ui.Button:
    for item in view.walk_children():
        if isinstance(item, discord.ui.Button) and item.custom_id == custom_id:
            return item
    raise AssertionError(f"button not found: {custom_id}")


def build_challenge_interaction(user_id: int = 100) -> tuple[discord.Interaction, FakeResponse]:
    response = FakeResponse()
    interaction = cast(
        discord.Interaction,
        SimpleNamespace(
            guild_id=200,
            user=SimpleNamespace(id=user_id),
            response=response,
        ),
    )
    return interaction, response


@pytest.mark.asyncio
async def test_auth_challenge_digit_buttons_update_and_limit_input() -> None:
    view = AuthChallengeView(cast(AsteroidBot, SimpleNamespace()), "12345", owner_id=100)
    interaction, response = build_challenge_interaction()

    for digit in ("1", "2", "3", "4", "5", "6"):
        await find_button(view, f"auth_digit:{digit}").callback(interaction)

    assert view.entered_number == "12345"
    assert len(response.edits) == 6
    container = cast(discord.ui.Container, view.children[0])
    text = cast(discord.ui.TextDisplay, container.children[0])
    assert "## **入力:** `12345`" in text.content


@pytest.mark.asyncio
async def test_auth_challenge_delete_clear_and_wrong_submit() -> None:
    view = AuthChallengeView(cast(AsteroidBot, SimpleNamespace()), "12345", owner_id=100)
    interaction, _ = build_challenge_interaction()
    view.entered_number = "120"

    await find_button(view, "auth_delete").callback(interaction)
    assert view.entered_number == "12"

    await find_button(view, "auth_clear").callback(interaction)
    assert view.entered_number == ""

    view.entered_number = "99999"
    await find_button(view, "auth_submit").callback(interaction)

    assert view.entered_number == ""
    assert view.error_message == "数字が一致しませんでした。もう一度入力してください。"
    container = cast(discord.ui.Container, view.children[0])
    text = cast(discord.ui.TextDisplay, container.children[0])
    assert view.error_message in text.content


@pytest.mark.asyncio
async def test_auth_challenge_correct_submit_completes_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeMember:
        def __init__(self, user_id: int) -> None:
            self.id = user_id

    completed_interactions: list[object] = []

    async def fake_complete_authentication(_: object, interaction: object) -> bool:
        completed_interactions.append(interaction)
        return True

    monkeypatch.setattr(auth_views.discord, "Member", FakeMember)
    monkeypatch.setattr(auth_views, "complete_authentication", fake_complete_authentication)

    view = AuthChallengeView(cast(AsteroidBot, SimpleNamespace()), "12345", owner_id=100)
    view.entered_number = "12345"
    response = FakeResponse()
    original_response_edits: list[dict[str, object]] = []

    async def edit_original_response(**kwargs: object) -> None:
        original_response_edits.append(kwargs)

    interaction = cast(
        discord.Interaction,
        SimpleNamespace(
            guild=SimpleNamespace(id=200),
            guild_id=200,
            user=FakeMember(100),
            response=response,
            edit_original_response=edit_original_response,
        ),
    )

    await find_button(view, "auth_submit").callback(interaction)

    assert completed_interactions == [interaction]
    assert response.defers == 1
    assert view.completed is True
    assert original_response_edits == [{"view": view}]
    container = cast(discord.ui.Container, view.children[0])
    text = cast(discord.ui.TextDisplay, container.children[0])
    assert "# 検証に成功しました！" in text.content


@pytest.mark.asyncio
async def test_auth_sends_captcha_file_with_components_v2_view(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeImageCaptcha:
        def __init__(self, *_: object) -> None:
            pass

        def generate(self, _: str, __: str) -> BytesIO:
            return BytesIO(b"captcha")

    monkeypatch.setattr(auth_views, "ImageCaptcha", FakeImageCaptcha)
    response = FakeResponse()
    interaction = cast(
        discord.Interaction,
        SimpleNamespace(
            guild=SimpleNamespace(id=100),
            channel_id=200,
            user=SimpleNamespace(id=300),
            response=response,
        ),
    )

    await auth_views.auth(cast(AsteroidBot, SimpleNamespace()), interaction)

    assert len(response.messages) == 1
    payload = response.messages[0]
    assert payload["ephemeral"] is True
    assert "embed" not in payload
    assert isinstance(payload["file"], discord.File)
    assert isinstance(payload["view"], AuthChallengeView)
