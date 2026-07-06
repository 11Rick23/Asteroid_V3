from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import discord
import pytest

from app.features.log import login
from app.features.log.login import LogIn


class _LogConfig:
    def __init__(self, channel_id: int) -> None:
        self.main_log_channel_id = channel_id


class _Config:
    def __init__(self, channel_id: int) -> None:
        self.log = _LogConfig(channel_id)


class _Avatar:
    url = "https://example.com/avatar.png"


class _User:
    id = 100
    display_avatar = _Avatar()
    created_at = datetime(2026, 6, 23, 0, 0, tzinfo=UTC)

    def __str__(self) -> str:
        return "Asteroid"


class _Channel:
    def __init__(self) -> None:
        self.sent_embeds: list[discord.Embed] = []

    async def send(self, *, embed: discord.Embed) -> None:
        self.sent_embeds.append(embed)


class _Bot:
    application_id = 999

    def __init__(self, *, channel_id: int, channel: _Channel | None = None, operating: bool = True) -> None:
        self.config = _Config(channel_id)
        self.channel = channel
        self.operating = operating
        self.user = _User()
        self.get_channel_calls: list[int] = []
        self.waited = False

    async def wait_until_ready(self) -> None:
        self.waited = True

    def get_channel(self, channel_id: int) -> _Channel | None:
        self.get_channel_calls.append(channel_id)
        return self.channel

    def is_operating_channel(self, channel: object) -> bool:
        return self.operating and channel is self.channel


@pytest.mark.asyncio
async def test_skips_unconfigured_channel():
    """ログイン通知チャンネルが未設定の場合は送信先解決を行わない。"""
    # 非機能要件：ログイン通知チャンネル未設定時は Discord 送信を試みない。
    # Given
    bot = _Bot(channel_id=0)
    cog = LogIn(cast(Any, bot))

    # When
    await cog.on_ready()

    # Then
    assert bot.waited is True
    assert bot.get_channel_calls == []


@pytest.mark.asyncio
async def test_sends_login_embed(monkeypatch):
    """ログイン通知は設定済みチャンネルへ BOT 情報の Embed を送信する。"""
    # 機能要件：ログイン完了時は設定済みログチャンネルへ BOT 情報の Embed を送信する。
    # 非機能要件：運用対象外チャンネルにはログイン通知を送信しない。
    # Given
    channel = _Channel()
    bot = _Bot(channel_id=10, channel=channel)
    cog = LogIn(cast(Any, bot))
    monkeypatch.setattr(login, "as_messageable", lambda channel: channel)

    # When
    await cog.on_ready()

    # Then
    assert bot.get_channel_calls == [10]
    assert len(channel.sent_embeds) == 1
    embed = channel.sent_embeds[0]
    assert embed.title == "ログイン完了！"
    assert str(bot.user) in (embed.description or "")
