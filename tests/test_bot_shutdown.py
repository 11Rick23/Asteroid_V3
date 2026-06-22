from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from app.common.offline import OfflineInfo
from app.core.bot import AsteroidBot


class FakeLogChannel(discord.abc.Messageable):
    def __init__(self, guild_id: int = 456) -> None:
        self.messages: list[dict[str, Any]] = []
        self.guild = SimpleNamespace(id=guild_id)

    async def send(self, content: str | None = None, **kwargs: Any) -> discord.Message:
        self.messages.append({"content": content, **kwargs})
        return None  # type: ignore[return-value]


class FakeBot:
    def __init__(self, channel_id: int, channel: FakeLogChannel | None = None) -> None:
        self.config = SimpleNamespace(
            discord=SimpleNamespace(guild_id=456),
            log=SimpleNamespace(main_log_channel_id=channel_id),
        )
        self.channel = channel
        self.fetched_channel: FakeLogChannel | None = None

    def is_operating_guild(self, guild: object) -> bool:
        return getattr(guild, "id", None) == self.config.discord.guild_id

    def is_operating_channel(self, channel: object) -> bool:
        return self.is_operating_guild(getattr(channel, "guild", None))

    def get_channel(self, channel_id: int) -> FakeLogChannel | None:
        return self.channel

    async def fetch_channel(self, channel_id: int) -> FakeLogChannel:
        if self.fetched_channel is None:
            self.fetched_channel = FakeLogChannel()
        return self.fetched_channel


class FakePanelManager:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    async def set_all_offline(self, info: OfflineInfo) -> dict[str, bool]:
        self.events.append(f"panels:{info.reason}:{info.planned_period}")
        return {"ranking": True}


class FakeShutdownBot:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.panels = FakePanelManager(self.events)
        self.shutdown_requested = True

    async def send_shutdown_start_message(self, info: OfflineInfo) -> None:
        self.events.append("log")

    async def set_offline_presence(self) -> None:
        self.events.append("presence")

    async def close(self) -> None:
        self.events.append("close")


@pytest.mark.asyncio
async def test_send_shutdown_start_message_uses_cached_log_channel() -> None:
    channel = FakeLogChannel()
    bot = FakeBot(123, channel)

    await AsteroidBot.send_shutdown_start_message(
        cast(AsteroidBot, bot),
        OfflineInfo(reason="SIGTERM シグナルによる強制停止", planned_period="未定"),
    )

    assert len(channel.messages) == 1
    embed = channel.messages[0]["embed"]
    assert embed.title == "BOT の停止処理を開始します"
    assert embed.description is None
    assert embed.fields[0].name == "理由"
    assert embed.fields[0].value == "SIGTERM シグナルによる強制停止"
    assert embed.fields[1].name == "予定期間"
    assert embed.fields[1].value == "未定"


@pytest.mark.asyncio
async def test_send_shutdown_start_message_fetches_missing_log_channel() -> None:
    bot = FakeBot(123)

    await AsteroidBot.send_shutdown_start_message(
        cast(AsteroidBot, bot),
        OfflineInfo(reason="メンテナンス", planned_period="1時間"),
    )

    assert bot.fetched_channel is not None
    assert len(bot.fetched_channel.messages) == 1
    embed = bot.fetched_channel.messages[0]["embed"]
    assert embed.title == "BOT の停止処理を開始します"
    assert embed.fields[0].value == "メンテナンス"
    assert embed.fields[1].value == "1時間"


@pytest.mark.asyncio
async def test_send_shutdown_start_message_skips_when_log_channel_is_not_configured() -> None:
    bot = FakeBot(0)

    await AsteroidBot.send_shutdown_start_message(
        cast(AsteroidBot, bot),
        OfflineInfo(reason="SIGTERM シグナルによる強制停止", planned_period="未定"),
    )

    assert bot.fetched_channel is None


@pytest.mark.asyncio
async def test_send_shutdown_start_message_skips_channel_in_other_guild() -> None:
    channel = FakeLogChannel(guild_id=999)
    bot = FakeBot(123, channel)

    await AsteroidBot.send_shutdown_start_message(
        cast(AsteroidBot, bot),
        OfflineInfo(reason="SIGTERM シグナルによる強制停止", planned_period="未定"),
    )

    assert channel.messages == []


@pytest.mark.asyncio
async def test_shutdown_gracefully_offlines_panels_before_other_shutdown_steps() -> None:
    bot = FakeShutdownBot()

    await AsteroidBot.shutdown_gracefully(
        cast(AsteroidBot, bot),
        OfflineInfo(reason="メンテナンス", planned_period="1時間"),
    )

    assert bot.events == [
        "panels:メンテナンス:1時間",
        "log",
        "presence",
        "close",
    ]
