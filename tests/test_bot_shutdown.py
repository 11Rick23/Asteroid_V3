from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import discord
import pytest

from app.core.bot import AsteroidBot


class FakeLogChannel(discord.abc.Messageable):
    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send(self, content: str | None = None, **kwargs: Any) -> discord.Message:
        self.messages.append({"content": content, **kwargs})
        return None  # type: ignore[return-value]


class FakeBot:
    def __init__(self, channel_id: int, channel: FakeLogChannel | None = None) -> None:
        self.config = SimpleNamespace(log=SimpleNamespace(main_log_channel_id=channel_id))
        self.channel = channel
        self.fetched_channel: FakeLogChannel | None = None

    def get_channel(self, channel_id: int) -> FakeLogChannel | None:
        return self.channel

    async def fetch_channel(self, channel_id: int) -> FakeLogChannel:
        if self.fetched_channel is None:
            self.fetched_channel = FakeLogChannel()
        return self.fetched_channel


@pytest.mark.asyncio
async def test_send_shutdown_start_message_uses_cached_log_channel() -> None:
    channel = FakeLogChannel()
    bot = FakeBot(123, channel)

    await AsteroidBot.send_shutdown_start_message(bot, "signal=SIGTERM")  # type: ignore[arg-type]

    assert len(channel.messages) == 1
    embed = channel.messages[0]["embed"]
    assert embed.title == "BOT の停止処理を開始します"
    assert embed.description is None
    assert embed.fields[0].name == "理由"
    assert embed.fields[0].value == "`signal=SIGTERM`"


@pytest.mark.asyncio
async def test_send_shutdown_start_message_fetches_missing_log_channel() -> None:
    bot = FakeBot(123)

    await AsteroidBot.send_shutdown_start_message(bot, "command=/stop")  # type: ignore[arg-type]

    assert bot.fetched_channel is not None
    assert len(bot.fetched_channel.messages) == 1
    embed = bot.fetched_channel.messages[0]["embed"]
    assert embed.title == "BOT の停止処理を開始します"
    assert embed.fields[0].value == "`command=/stop`"


@pytest.mark.asyncio
async def test_send_shutdown_start_message_skips_when_log_channel_is_not_configured() -> None:
    bot = FakeBot(0)

    await AsteroidBot.send_shutdown_start_message(bot, "signal=SIGTERM")  # type: ignore[arg-type]

    assert bot.fetched_channel is None
