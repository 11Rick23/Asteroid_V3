from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest
from discord import app_commands

from app.core.bot import AsteroidBot
from app.features.log.error import DEFAULT_ERROR_MESSAGE, RATE_LIMITED_ERROR_MESSAGE, Error


class FakeResponse:
    def __init__(self, *, done: bool = False) -> None:
        self.done = done
        self.messages: list[dict[str, object]] = []

    def is_done(self) -> bool:
        return self.done

    async def send_message(self, **kwargs: object) -> None:
        self.messages.append(kwargs)


class FakeFollowup:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send(self, **kwargs: object) -> None:
        self.messages.append(kwargs)


class FakeBot:
    def __init__(self, log_channel: FakeLogChannel | None = None) -> None:
        self.log_channel = log_channel
        self.config = SimpleNamespace(log=SimpleNamespace(main_log_channel_id=123 if log_channel else 0))

    def get_channel(self, channel_id: int) -> FakeLogChannel | None:
        return self.log_channel

    def is_operating_channel(self, channel: object) -> bool:
        return channel is self.log_channel


class FakeLogChannel(discord.abc.Messageable):
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send(self, content: str | None = None, **kwargs: Any) -> discord.Message:
        self.messages.append({"content": content, **kwargs})
        return cast(discord.Message, None)


def make_interaction(*, response_done: bool = False) -> tuple[discord.Interaction, FakeResponse, FakeFollowup]:
    response = FakeResponse(done=response_done)
    followup = FakeFollowup()
    interaction = SimpleNamespace(
        command=SimpleNamespace(qualified_name="test"),
        user=SimpleNamespace(id=123, __str__=lambda self: "test-user"),
        guild_id=456,
        channel_id=789,
        response=response,
        followup=followup,
    )
    return cast(discord.Interaction, interaction), response, followup


@pytest.mark.asyncio
async def test_unexpected_error_sends_error_and_traceback_embeds() -> None:
    interaction, response, _ = make_interaction()
    cog = Error(cast(AsteroidBot, FakeBot()))
    exception = app_commands.AppCommandError("unexpected")

    await cog.on_app_command_error(interaction, exception)

    assert len(response.messages) == 1
    assert response.messages[0]["ephemeral"] is True
    embeds = cast(list[discord.Embed], response.messages[0]["embeds"])
    assert len(embeds) == 2
    assert embeds[0].title == "エラー"
    assert embeds[0].description == DEFAULT_ERROR_MESSAGE
    assert embeds[1].title == "トレースバック"
    assert "AppCommandError: unexpected" in (embeds[1].description or "")


@pytest.mark.asyncio
async def test_expected_error_sends_only_error_embed() -> None:
    interaction, response, _ = make_interaction()
    cog = Error(cast(AsteroidBot, FakeBot()))

    await cog.on_app_command_error(interaction, app_commands.CheckFailure())

    embeds = cast(list[discord.Embed], response.messages[0]["embeds"])
    assert len(embeds) == 1
    assert embeds[0].title == "エラー"
    assert embeds[0].description == "このコマンドを実行する権限がありません。"


@pytest.mark.asyncio
async def test_rate_limited_error_sends_only_retry_message(caplog: pytest.LogCaptureFixture) -> None:
    interaction, response, _ = make_interaction()
    cog = Error(cast(AsteroidBot, FakeBot()))
    exception = app_commands.CommandInvokeError(
        cast(app_commands.Command[Any, ..., Any], SimpleNamespace(name="test")),
        discord.RateLimited(3.8),
    )

    await cog.on_app_command_error(interaction, exception)

    assert len(response.messages) == 1
    assert response.messages[0]["ephemeral"] is True
    embeds = cast(list[discord.Embed], response.messages[0]["embeds"])
    assert len(embeds) == 1
    assert embeds[0].title == "エラー"
    assert embeds[0].description == RATE_LIMITED_ERROR_MESSAGE.format(retry_after=3.8)
    assert "App command rate limited" in caplog.text
    assert "retry_after=3.8" in caplog.text
    assert "App command failed" not in caplog.text


@pytest.mark.asyncio
async def test_completed_interaction_uses_followup_with_two_embeds() -> None:
    interaction, _, followup = make_interaction(response_done=True)
    cog = Error(cast(AsteroidBot, FakeBot()))

    await cog.on_app_command_error(interaction, app_commands.AppCommandError("unexpected"))

    assert len(followup.messages) == 1
    embeds = cast(list[discord.Embed], followup.messages[0]["embeds"])
    assert len(embeds) == 2


@pytest.mark.asyncio
async def test_log_channel_receives_error_and_traceback_embeds() -> None:
    interaction, _, _ = make_interaction()
    log_channel = FakeLogChannel()
    cog = Error(cast(AsteroidBot, FakeBot(log_channel)))

    await cog.on_app_command_error(interaction, app_commands.AppCommandError("unexpected"))

    assert len(log_channel.messages) == 1
    embeds = cast(list[discord.Embed], log_channel.messages[0]["embeds"])
    assert len(embeds) == 2
    assert embeds[0].title == "アプリコマンドエラー"
    assert [field.name for field in embeds[0].fields] == [
        "コマンド",
        "ユーザー",
        "サーバー / チャンネル",
    ]
    assert embeds[1].title == "トレースバック"
