from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from app.common.guild_scope import (
    OUTSIDE_OPERATING_GUILD_MESSAGE,
    GuildScopedLayoutView,
    GuildScopedModal,
    GuildScopedView,
    OperatingGuildCommandTree,
    OutsideOperatingGuild,
)
from app.common.interaction_errors import RATE_LIMITED_ERROR_MESSAGE, UI_ERROR_MESSAGE
from app.core.bot import AsteroidBot
from app.core.config import AsteroidConfig, DatabaseConfig, DiscordConfig
from app.features.log.error import Error
from app.features.starboard.cog import Starboard
from app.features.vc.cog import VoiceCreateCog


class FakeResponse:
    def __init__(self) -> None:
        self.messages: list[tuple[str, bool]] = []

    def is_done(self) -> bool:
        return False

    async def send_message(self, content: str, *, ephemeral: bool = False) -> None:
        self.messages.append((content, ephemeral))


class FakeErrorResponse:
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


class FakeLogChannel(discord.abc.Messageable):
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send(self, content: str | None = None, **kwargs: Any) -> discord.Message:
        self.messages.append({"content": content, **kwargs})
        return cast(discord.Message, None)


class FakeErrorBot:
    def __init__(self, log_channel: FakeLogChannel | None = None) -> None:
        self.log_channel = log_channel
        self.config = SimpleNamespace(
            discord=SimpleNamespace(guild_id=100),
            log=SimpleNamespace(main_log_channel_id=123 if log_channel else 0),
        )

    def get_channel(self, channel_id: int) -> FakeLogChannel | None:
        return self.log_channel

    def is_operating_channel(self, channel: object) -> bool:
        return channel is self.log_channel


def build_interaction(guild_id: int | None) -> Any:
    return SimpleNamespace(
        client=SimpleNamespace(config=SimpleNamespace(discord=SimpleNamespace(guild_id=100))),
        guild_id=guild_id,
        channel_id=200,
        user=SimpleNamespace(id=300),
        response=FakeResponse(),
    )


def build_error_interaction(
    *,
    response_done: bool = False,
    log_channel: FakeLogChannel | None = None,
) -> tuple[discord.Interaction, FakeErrorResponse, FakeFollowup]:
    response = FakeErrorResponse(done=response_done)
    followup = FakeFollowup()
    interaction = SimpleNamespace(
        client=FakeErrorBot(log_channel),
        guild_id=100,
        channel_id=200,
        user=SimpleNamespace(id=300),
        response=response,
        followup=followup,
    )
    return cast(discord.Interaction, interaction), response, followup


@pytest.mark.asyncio
async def test_command_tree_allows_only_operating_guild() -> None:
    client = discord.Client(intents=discord.Intents.none())
    client.config = SimpleNamespace(discord=SimpleNamespace(guild_id=100))  # type: ignore[attr-defined]
    tree = OperatingGuildCommandTree(client)

    assert await tree.interaction_check(cast(discord.Interaction, build_interaction(100))) is True
    with pytest.raises(OutsideOperatingGuild):
        await tree.interaction_check(cast(discord.Interaction, build_interaction(101)))
    with pytest.raises(OutsideOperatingGuild):
        await tree.interaction_check(cast(discord.Interaction, build_interaction(None)))


@pytest.mark.asyncio
@pytest.mark.parametrize("component", [GuildScopedView(), GuildScopedModal(title="test")])
async def test_ui_rejects_outside_operating_guild(component: GuildScopedView | GuildScopedModal) -> None:
    interaction = build_interaction(101)

    assert await component.interaction_check(cast(discord.Interaction, interaction)) is False
    assert interaction.response.messages == [(OUTSIDE_OPERATING_GUILD_MESSAGE, True)]


@pytest.mark.asyncio
async def test_layout_view_rate_limited_error_sends_ephemeral_retry_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    log_channel = FakeLogChannel()
    interaction, response, _ = build_error_interaction(log_channel=log_channel)
    view = GuildScopedLayoutView()

    await view.on_error(
        interaction,
        discord.RateLimited(3.8),
        cast(discord.ui.Item[Any], object()),
    )

    assert len(response.messages) == 1
    assert response.messages[0]["ephemeral"] is True
    embeds = cast(list[discord.Embed], response.messages[0]["embeds"])
    assert len(embeds) == 1
    assert embeds[0].title == "エラー"
    assert embeds[0].description == RATE_LIMITED_ERROR_MESSAGE.format(retry_after=3.8)
    assert "UI interaction rate limited" in caplog.text
    assert "retry_after=3.8" in caplog.text
    assert log_channel.messages == []


@pytest.mark.asyncio
async def test_modal_rate_limited_error_sends_ephemeral_retry_message() -> None:
    interaction, response, _ = build_error_interaction()
    modal = GuildScopedModal(title="test")

    await modal.on_error(interaction, discord.RateLimited(2.4))

    embeds = cast(list[discord.Embed], response.messages[0]["embeds"])
    assert response.messages[0]["ephemeral"] is True
    assert embeds[0].description == RATE_LIMITED_ERROR_MESSAGE.format(retry_after=2.4)


@pytest.mark.asyncio
async def test_ui_unexpected_error_sends_only_common_error_embed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    log_channel = FakeLogChannel()
    interaction, response, _ = build_error_interaction(log_channel=log_channel)
    view = GuildScopedLayoutView()

    await view.on_error(
        interaction,
        RuntimeError("unexpected"),
        cast(discord.ui.Item[Any], object()),
    )

    assert len(response.messages) == 1
    assert response.messages[0]["ephemeral"] is True
    embeds = cast(list[discord.Embed], response.messages[0]["embeds"])
    assert len(embeds) == 1
    assert embeds[0].title == "エラー"
    assert embeds[0].description == UI_ERROR_MESSAGE
    assert "トレースバック" not in (embeds[0].description or "")
    assert "UI interaction failed" in caplog.text
    assert len(log_channel.messages) == 1
    log_embeds = cast(list[discord.Embed], log_channel.messages[0]["embeds"])
    assert log_embeds[0].title == "UI操作エラー"
    assert log_embeds[1].title == "トレースバック"


@pytest.mark.asyncio
async def test_completed_ui_interaction_error_uses_followup() -> None:
    interaction, response, followup = build_error_interaction(response_done=True)
    view = GuildScopedLayoutView()

    await view.on_error(
        interaction,
        RuntimeError("unexpected"),
        cast(discord.ui.Item[Any], object()),
    )

    assert response.messages == []
    assert len(followup.messages) == 1
    embeds = cast(list[discord.Embed], followup.messages[0]["embeds"])
    assert followup.messages[0]["ephemeral"] is True
    assert embeds[0].description == UI_ERROR_MESSAGE


@pytest.mark.asyncio
async def test_error_handler_treats_outside_guild_as_expected_denial(
    caplog: pytest.LogCaptureFixture,
) -> None:
    bot = cast(AsteroidBot, SimpleNamespace())
    interaction = build_interaction(101)

    await Error(bot).on_app_command_error(
        cast(discord.Interaction, interaction),
        OutsideOperatingGuild(),
    )

    assert interaction.response.messages == [(OUTSIDE_OPERATING_GUILD_MESSAGE, True)]
    assert "App command failed" not in caplog.text


def test_bot_rejects_missing_operating_guild_id() -> None:
    with pytest.raises(RuntimeError, match="guild_id"):
        AsteroidBot(AsteroidConfig())


def test_bot_sets_short_http_rate_limit_timeout() -> None:
    bot = AsteroidBot(
        AsteroidConfig(
            discord=DiscordConfig(guild_id=100),
            database=DatabaseConfig(url="mysql+aiomysql://user:password@127.0.0.1/test_db"),
        )
    )

    assert bot.http.max_ratelimit_timeout == 3.0


@pytest.mark.asyncio
async def test_starboard_does_not_cache_messages_from_other_guilds() -> None:
    remembered: list[object] = []
    bot = SimpleNamespace(
        is_operating_guild=lambda guild: guild.id == 100,
        remember_message=remembered.append,
    )
    cog = Starboard(cast(AsteroidBot, bot))

    await cog.on_message(SimpleNamespace(guild=SimpleNamespace(id=101)))  # type: ignore[arg-type]

    assert remembered == []


@pytest.mark.asyncio
async def test_voice_event_does_not_call_service_for_other_guild() -> None:
    calls: list[tuple[object, object, object]] = []

    class FakeService:
        async def handle_voice_state_update(self, member: object, before: object, after: object) -> None:
            calls.append((member, before, after))

    bot = SimpleNamespace(
        is_operating_guild=lambda guild: guild.id == 100,
        services={"vc": FakeService()},
    )
    cog = VoiceCreateCog(cast(AsteroidBot, bot))
    cog.service = cast(Any, FakeService())
    member = SimpleNamespace(guild=SimpleNamespace(id=101))

    await cog.on_voice_state_update(member, object(), object())  # type: ignore[arg-type]

    assert calls == []
