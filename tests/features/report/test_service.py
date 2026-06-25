from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from app.features.report.service import build_report_embed, build_resolved_report_embed


@dataclass(slots=True)
class _Avatar:
    url: str


@dataclass(slots=True)
class _User:
    display_name: str
    display_avatar: _Avatar


def test_builds_report_embed():
    """通報 Embed は本文、通報者、未対応 footer、添付画像を含める。"""
    # 機能要件：通報 Embed には本文、通報者、対応状態、添付画像を含める。
    # Given
    reporter = _User("reporter", _Avatar("https://example.com/avatar.png"))
    image = type("FakeAttachment", (), {"url": "https://example.com/image.png"})()

    # When
    embed = build_report_embed(cast(Any, reporter), "違反内容", cast(Any, image))

    # Then
    assert embed.description == "違反内容"
    assert embed.author.name == "reporter"
    assert embed.footer.text == "未対応"
    assert embed.image.url == "https://example.com/image.png"


def test_resolves_report_embed():
    """対応済み Embed は footer を moderator 情報へ差し替える。"""
    # 機能要件：通報の対応済み表示では moderator 情報を footer に反映する。
    # Given
    moderator = _User("moderator", _Avatar("https://example.com/mod.png"))
    embed = build_report_embed(cast(Any, _User("reporter", _Avatar("avatar"))), "違反内容")

    # When
    resolved = build_resolved_report_embed(embed, cast(Any, moderator))

    # Then
    assert resolved.description == "違反内容"
    assert resolved.footer.text == "moderator によって対応済み"
    assert resolved.footer.icon_url == "https://example.com/mod.png"
