from __future__ import annotations

import discord
import pytest

from app.core.system_commands import stop_bot


class FakeResponse:
    def __init__(self) -> None:
        self.messages: list[tuple[str, bool]] = []

    async def send_message(self, content: str, *, ephemeral: bool = False) -> None:
        self.messages.append((content, ephemeral))


class FakeUser:
    id = 123


class FakeBot:
    def __init__(self) -> None:
        self.shutdown_requested = False
        self.shutdown_task = None
        self.close_count = 0
        self.events: list[str] = []
        self.presence_changes: list[tuple[discord.Status, object | None]] = []

    async def change_presence(self, *, status: discord.Status, activity: object | None = None) -> None:
        self.events.append("change_presence")
        self.presence_changes.append((status, activity))

    async def close(self) -> None:
        self.events.append("close")
        self.close_count += 1

    async def shutdown_gracefully(self, reason: str) -> None:
        self.events.append(reason)
        await self.change_presence(status=discord.Status.offline, activity=None)
        await self.close()


class FakeInteraction:
    def __init__(self, bot: FakeBot) -> None:
        self.client = bot
        self.guild_id = 456
        self.channel_id = 789
        self.user = FakeUser()
        self.response = FakeResponse()


@pytest.mark.asyncio
async def test_stop_command_sends_ack_and_schedules_shutdown() -> None:
    bot = FakeBot()
    interaction = FakeInteraction(bot)

    await stop_bot.callback(interaction)  # type: ignore[arg-type]

    assert interaction.response.messages == [("BOT の停止処理を開始します。", True)]
    assert bot.shutdown_requested is True
    assert bot.shutdown_task is not None

    await bot.shutdown_task

    assert bot.close_count == 1
    assert bot.events == ["command=/stop", "change_presence", "close"]
    assert bot.presence_changes == [(discord.Status.offline, None)]


@pytest.mark.asyncio
async def test_stop_command_rejects_duplicate_shutdown() -> None:
    bot = FakeBot()
    bot.shutdown_requested = True
    interaction = FakeInteraction(bot)

    await stop_bot.callback(interaction)  # type: ignore[arg-type]

    assert interaction.response.messages == [("BOT は既に停止処理中です。", True)]
    assert bot.shutdown_task is None
    assert bot.close_count == 0
