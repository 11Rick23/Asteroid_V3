from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from app.common.guild_scope import (
    OUTSIDE_OPERATING_GUILD_MESSAGE,
    GuildScopedModal,
    GuildScopedView,
    OperatingGuildCommandTree,
    OutsideOperatingGuild,
)
from app.core.bot import AsteroidBot
from app.core.config import AsteroidConfig
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


def build_interaction(guild_id: int | None) -> Any:
    return SimpleNamespace(
        client=SimpleNamespace(config=SimpleNamespace(discord=SimpleNamespace(guild_id=100))),
        guild_id=guild_id,
        channel_id=200,
        user=SimpleNamespace(id=300),
        response=FakeResponse(),
    )


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
