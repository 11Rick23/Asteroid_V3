from __future__ import annotations

import asyncio
import logging

import discord
import pytest

from app.common.offline import OfflineInfo
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

    async def shutdown_gracefully(self, info: OfflineInfo) -> None:
        self.events.append(f"{info.reason}:{info.planned_period}")
        await self.change_presence(status=discord.Status.offline, activity=None)
        await self.close()

    def schedule_graceful_shutdown(self, info: OfflineInfo) -> bool:
        if self.shutdown_requested:
            return False

        self.shutdown_requested = True
        self.shutdown_task = asyncio.create_task(self.shutdown_gracefully(info))
        return True


class FakeInteraction:
    def __init__(self, bot: FakeBot) -> None:
        self.client = bot
        self.guild_id = 456
        self.channel_id = 789
        self.user = FakeUser()
        self.response = FakeResponse()


def test_stop_command_requires_reason_and_planned_period() -> None:
    parameters = {parameter.name: parameter for parameter in stop_bot.parameters}

    assert parameters["reason"].display_name == "理由"
    assert parameters["reason"].required is True
    assert parameters["planned_period"].display_name == "予定期間"
    assert parameters["planned_period"].required is True


@pytest.mark.asyncio
async def test_stop_command_sends_ack_logs_and_schedules_shutdown(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bot = FakeBot()
    interaction = FakeInteraction(bot)

    with caplog.at_level(logging.INFO, logger="app.core.system_commands"):
        await stop_bot.callback(interaction, "メンテナンス", "1時間")  # type: ignore[arg-type]

    assert interaction.response.messages == [("BOT の停止処理を開始します。", True)]
    assert bot.shutdown_requested is True
    assert bot.shutdown_task is not None
    assert (
        "BOT 停止コマンドを受け付けました: command=/stop "
        "guild_id=456 channel_id=789 actor_id=123 reason=メンテナンス planned_period=1時間"
    ) in caplog.text

    await bot.shutdown_task

    assert bot.close_count == 1
    assert bot.events == ["メンテナンス:1時間", "change_presence", "close"]
    assert bot.presence_changes == [(discord.Status.offline, None)]


@pytest.mark.asyncio
async def test_stop_command_rejects_duplicate_shutdown(caplog: pytest.LogCaptureFixture) -> None:
    bot = FakeBot()
    bot.shutdown_requested = True
    interaction = FakeInteraction(bot)

    with caplog.at_level(logging.INFO, logger="app.core.system_commands"):
        await stop_bot.callback(interaction, "メンテナンス", "1時間")  # type: ignore[arg-type]

    assert interaction.response.messages == [("BOT は既に停止処理中です。", True)]
    assert bot.shutdown_task is None
    assert bot.close_count == 0
    assert (
        "BOT 停止コマンドを拒否しました: command=/stop reason=already_requested "
        "guild_id=456 channel_id=789 actor_id=123"
    ) in caplog.text
