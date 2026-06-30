from __future__ import annotations

from typing import Any, cast

import pytest

from app.features.vc.views import TogglePrivacyButton, member_mentions
from tests.support.discord_fakes import FakeUser


class _Response:
    def __init__(self) -> None:
        self.deferred = False

    async def defer(self, **_: object) -> None:
        self.deferred = True


class _Followup:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []

    async def send(self, content: str | None = None, **kwargs: object) -> None:
        self.sent_messages.append({"content": content, **kwargs})


class _Interaction:
    def __init__(self) -> None:
        self.user = FakeUser(100)
        self.response = _Response()
        self.followup = _Followup()


class _Service:
    def __init__(self) -> None:
        self.set_private_calls = 0
        self.refresh_calls = 0

    def is_private_channel(self, _channel: object) -> bool:
        return False

    async def ensure_voice_channel(self, *_: object, **__: object) -> None:
        return None

    async def set_private(self, *_: object, **__: object) -> None:
        self.set_private_calls += 1

    async def refresh_control_message(self, *_: object, **__: object) -> None:
        self.refresh_calls += 1


def test_formats_empty_member_mentions():
    """選択メンバーが空の場合は空文字ではなく「なし」と表示する。"""
    # 機能要件：VC のメンバー一覧表示は対象が空の場合に「なし」と表示する。
    # Given / When / Then
    assert member_mentions([]) == "なし"


@pytest.mark.asyncio
async def test_privacy_toggle_skips_invalid_channel():
    """VC 操作対象が解決できない場合は公開設定を変更しない。"""
    # 非機能要件：VC 操作対象が解決できない場合はチャンネル権限やパネルを更新しない。
    # Given
    service = _Service()
    button = TogglePrivacyButton(cast(Any, service))
    interaction = _Interaction()

    # When
    await button.callback(cast(Any, interaction))

    # Then
    assert interaction.response.deferred is True
    assert service.set_private_calls == 0
    assert service.refresh_calls == 0
    assert interaction.followup.sent_messages == []
