from __future__ import annotations

import re

from app.features.link_expander.cog import IMAGE_FILE_EXTENSION, discord_message_url_pattern


def test_matches_message_url():
    """Discord message URL から channel ID と message ID を抽出する。"""
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
    # Given
    url = "<https://discord.com/channels/123456789012345678/234567890123456789/345678901234567890>"

    # When / Then
    assert re.search(discord_message_url_pattern, url) is None


def test_recognizes_image_extension():
    """添付ファイルの画像判定は主要な画像拡張子を小文字で扱う。"""
    # Given / When / Then
    assert ".png" in IMAGE_FILE_EXTENSION
    assert ".webp" in IMAGE_FILE_EXTENSION
