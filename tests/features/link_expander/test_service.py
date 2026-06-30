from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from app.features.link_expander.cog import IMAGE_FILE_EXTENSION, LinkExpander, discord_message_url_pattern


@dataclass(slots=True)
class _Avatar:
    url: str


@dataclass(slots=True)
class _Author:
    display_name: str = "author"
    display_avatar: _Avatar = field(default_factory=lambda: _Avatar("https://example.com/avatar.png"))


@dataclass(slots=True)
class _Attachment:
    filename: str
    url: str


class _Channel:
    id = 10
    name = "general"


class _Message:
    content = "referenced body"
    created_at = datetime(2026, 6, 23, tzinfo=UTC)
    jump_url = "https://discord.com/channels/1/2/3"
    author = _Author()
    channel = _Channel()
    guild = None
    embeds: list[object] = []
    attachments = [
        _Attachment(filename="image.PNG", url="https://example.com/image.png"),
        _Attachment(filename="memo.txt", url="https://example.com/memo.txt"),
    ]


class _Bot:
    def __init__(self, *, operating: bool) -> None:
        self.operating = operating
        self.remembered_messages: list[object] = []

    def is_operating_guild(self, _guild: object) -> bool:
        return self.operating

    def remember_message(self, message: object) -> None:
        self.remembered_messages.append(message)


class _IncomingAuthor:
    bot = False


class _IncomingMessage:
    author = _IncomingAuthor()
    guild = object()
    content = "https://discord.com/channels/123456789012345678/234567890123456789/345678901234567890"


def test_matches_message_url():
    """Discord message URL から channel ID と message ID を抽出する。"""
    # 機能要件：Discord message URL から展開対象の channel ID と message ID を抽出する。
    # Given
    url = "https://discord.com/channels/123456789012345678/234567890123456789/345678901234567890"

    # When
    match = re.search(discord_message_url_pattern, url)

    # Then
    assert match is not None
    assert match.group("channel") == "234567890123456789"
    assert match.group("message") == "345678901234567890"


def test_ignores_embedded_url():
    """既に埋め込み抑制された URL はリンク展開対象にしない。"""
    # 非機能要件：ユーザーが埋め込み抑制した URL を自動展開しない。
    # Given
    url = "<https://discord.com/channels/123456789012345678/234567890123456789/345678901234567890>"

    # When / Then
    assert re.search(discord_message_url_pattern, url) is None


def test_recognizes_image_extension():
    """添付ファイルの画像判定は主要な画像拡張子を小文字で扱う。"""
    # 機能要件：リンク展開時の添付画像判定で主要な画像拡張子を扱う。
    # Given / When / Then
    assert ".png" in IMAGE_FILE_EXTENSION
    assert ".webp" in IMAGE_FILE_EXTENSION


def test_builds_reference_embed():
    """参照メッセージの Embed は本文、画像添付、通常添付ファイルを含める。"""
    # 機能要件：リンク展開 Embed には参照メッセージの本文、画像、添付ファイルを反映する。
    # Given
    expander = LinkExpander(cast(Any, object()))

    # When
    embeds = expander.generate_embed(cast(Any, _Message()), allow_nsfw=True)

    # Then
    assert len(embeds) == 1
    embed = embeds[0]
    assert embed.description == "referenced body"
    assert embed.image.url == "https://example.com/image.png"
    assert embed.fields[0].value is not None
    assert "memo.txt" in embed.fields[0].value


@pytest.mark.asyncio
async def test_skips_outside_guild():
    """対象外 guild のメッセージではリンク展開処理を開始しない。"""
    # 非機能要件：対象外 guild のメッセージでは message cache を更新しない。
    # Given
    bot = _Bot(operating=False)
    expander = LinkExpander(cast(Any, bot))

    # When
    await expander.link_expander(cast(Any, _IncomingMessage()))

    # Then
    assert bot.remembered_messages == []
