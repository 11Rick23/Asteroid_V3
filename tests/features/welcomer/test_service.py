from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import pytest

from app.features.welcomer import service


@dataclass(slots=True)
class _AuthConfig:
    welcome_channel_id: int = 10
    welcome_ping_role_id: int = 20


@dataclass(slots=True)
class _Config:
    auth: _AuthConfig


class _Channel:
    id = 10

    def __init__(self) -> None:
        self.sent_messages: list[str] = []

    async def send(self, content: str) -> None:
        self.sent_messages.append(content)


class _Guild:
    id = 12345

    def __init__(self, channel: _Channel | None) -> None:
        self.channel = channel
        self.requested_channel_ids: list[int] = []

    def get_channel(self, channel_id: int) -> _Channel | None:
        self.requested_channel_ids.append(channel_id)
        return self.channel if channel_id == 10 else None


@dataclass(slots=True)
class _Member:
    guild: _Guild
    id: int = 100
    mention: str = "<@100>"


@pytest.mark.asyncio
async def test_sends_first_welcome(monkeypatch):
    """初回ウェルカムは設定済みチャンネルへ member mention と通知ロールを含めて送信する。"""
    # 機能要件：初回参加者にはウェルカムチャンネルで歓迎メッセージを送信する。
    # 機能要件：通知ロールが設定されている場合は送信内容に含める。
    # Given
    channel = _Channel()
    member = _Member(guild=_Guild(channel))
    monkeypatch.setattr(service, "get_config", lambda: _Config(auth=_AuthConfig()))
    monkeypatch.setattr(service, "as_messageable", lambda channel: channel)

    # When
    await service.send_first_welcome(cast(Any, member))

    # Then
    assert len(channel.sent_messages) == 1
    assert "<@100>" in channel.sent_messages[0]
    assert "<@&20>" in channel.sent_messages[0]


@pytest.mark.asyncio
async def test_skips_missing_channel(monkeypatch):
    """ウェルカム送信先が見つからない場合はメッセージ送信を行わない。"""
    # 非機能要件：設定されたウェルカム送信先が解決できない場合は送信を試みない。
    # Given
    member = _Member(guild=_Guild(channel=None))
    monkeypatch.setattr(service, "get_config", lambda: _Config(auth=_AuthConfig()))
    monkeypatch.setattr(service, "as_messageable", lambda channel: channel)

    # When
    await service.send_return_welcome(cast(Any, member))

    # Then
    assert member.guild.requested_channel_ids == [10]
