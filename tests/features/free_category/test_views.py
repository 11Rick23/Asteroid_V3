from __future__ import annotations

from typing import Any, cast

import pytest

from app.features.free_category.views import CreateChannelButton, CreateChannelModal
from tests.support.discord_fakes import FakeUser


class _Response:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []
        self.sent_modals: list[object] = []

    async def send_message(self, content: str | None = None, **kwargs: object) -> None:
        self.sent_messages.append({"content": content, **kwargs})

    async def send_modal(self, modal: object) -> None:
        self.sent_modals.append(modal)


class _Interaction:
    def __init__(self) -> None:
        self.user = FakeUser(100)
        self.response = _Response()


class _Service:
    def __init__(self, *, on_cooldown: bool) -> None:
        self.on_cooldown = on_cooldown

    def is_creation_on_cooldown(self, user_id: int) -> bool:
        assert user_id == 100
        return self.on_cooldown

    def get_creation_cooldown_seconds(self) -> int:
        return 7200


@pytest.mark.asyncio
async def test_rejects_creation_cooldown():
    """作成クールダウン中のユーザーには作成 modal を出さず、本人向けに拒否通知する。"""
    # 非機能要件：作成クールダウン中はチャンネル作成 modal を開かない。
    # Given
    button = CreateChannelButton(cast(Any, _Service(on_cooldown=True)))
    interaction = _Interaction()

    # When
    await button.callback(cast(Any, interaction))

    # Then
    assert interaction.response.sent_modals == []
    assert len(interaction.response.sent_messages) == 1
    assert interaction.response.sent_messages[0]["ephemeral"] is True


@pytest.mark.asyncio
async def test_opens_creation_modal():
    """作成クールダウン外のユーザーにはフリーチャンネル作成 modal を表示する。"""
    # 機能要件：作成可能なユーザーにはチャンネル作成 modal を開く。
    # Given
    button = CreateChannelButton(cast(Any, _Service(on_cooldown=False)))
    interaction = _Interaction()

    # When
    await button.callback(cast(Any, interaction))

    # Then
    assert interaction.response.sent_messages == []
    assert isinstance(interaction.response.sent_modals[0], CreateChannelModal)
