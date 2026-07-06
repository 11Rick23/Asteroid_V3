from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from app.features.starboard.cog import Starboard


@dataclass(slots=True)
class _Attachment:
    filename: str
    url: str


@dataclass(slots=True)
class _Channel:
    id: int = 10
    mention: str = "<#10>"


class _Message:
    id = 100
    content = "starred content"
    created_at = datetime(2026, 6, 23, tzinfo=UTC)
    attachments = [
        _Attachment(filename="image.png", url="https://example.com/image.png"),
        _Attachment(filename="memo.txt", url="https://example.com/memo.txt"),
    ]
    channel = _Channel()


class _Bot:
    def __init__(self, *, operating: bool) -> None:
        self.operating = operating
        self.remembered_messages: list[object] = []

    def is_operating_guild(self, _guild: object) -> bool:
        return self.operating

    def remember_message(self, message: object) -> None:
        self.remembered_messages.append(message)


@pytest.mark.asyncio
async def test_builds_starboard_entry():
    """スターボード投稿は星数、元チャンネル、本文、添付画像、添付ファイルを含める。"""
    # 機能要件：スターボード投稿には星数、元チャンネル、本文、添付情報を反映する。
    # Given
    cog = Starboard(cast(Any, object()))

    # When
    content, embed = await cog._build_starboard(cast(Any, _Message()), star_amount=6)

    # Then
    assert "6" in content
    assert "<#10>" in content
    assert embed.description == "starred content"
    assert embed.image.url == "https://example.com/image.png"
    assert embed.fields[0].value == "https://example.com/memo.txt"


def test_switches_star_emoji():
    """スターボードの星アイコンは 10 個以上で強調表示に切り替える。"""
    # 機能要件：スターボード表示は星数 10 個以上で強調アイコンへ切り替える。
    # Given
    cog = Starboard(cast(Any, object()))

    # When / Then
    assert cog.get_star_emoji(9) == "🌟"
    assert cog.get_star_emoji(10) == "💫"


@pytest.mark.asyncio
async def test_skips_outside_guild():
    """対象外 guild の message ではスターボード用 message cache を更新しない。"""
    # 非機能要件：対象外 guild の message では message cache を更新しない。
    # Given
    bot = _Bot(operating=False)
    cog = Starboard(cast(Any, bot))
    message = type("FakeMessage", (), {"guild": object()})()

    # When
    await cog.on_message(cast(Any, message))

    # Then
    assert bot.remembered_messages == []
