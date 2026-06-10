from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import cast

import discord
import pytest

from app.core.bot import AsteroidBot
from app.features.rolepanel.runtime import RolePanelCog
from app.features.rolepanel.service import RolePanelService


class FakeRolePanelService:
    def __init__(self) -> None:
        self.members: list[discord.Member] = []

    async def remove_boost_required_roles(self, member: discord.Member) -> None:
        self.members.append(member)


def build_cog(service: FakeRolePanelService) -> RolePanelCog:
    cog = object.__new__(RolePanelCog)
    cog.bot = cast(
        AsteroidBot,
        SimpleNamespace(is_operating_guild=lambda guild: guild.id == 100),
    )
    cog.service = cast(RolePanelService, service)
    return cog


@pytest.mark.asyncio
async def test_member_update_removes_boost_roles_when_boost_ends() -> None:
    service = FakeRolePanelService()
    cog = build_cog(service)
    guild = SimpleNamespace(id=100)
    before = cast(discord.Member, SimpleNamespace(id=200, guild=guild, premium_since=datetime.now()))
    after = cast(discord.Member, SimpleNamespace(id=200, guild=guild, premium_since=None))

    await cog.on_member_update(before, after)

    assert service.members == [after]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("before_premium_since", "after_premium_since", "guild_id"),
    [
        (None, None, 100),
        (None, datetime.now(), 100),
        (datetime.now(), datetime.now(), 100),
        (datetime.now(), None, 999),
    ],
)
async def test_member_update_ignores_updates_without_operating_guild_boost_end(
    before_premium_since: datetime | None,
    after_premium_since: datetime | None,
    guild_id: int,
) -> None:
    service = FakeRolePanelService()
    cog = build_cog(service)
    guild = SimpleNamespace(id=guild_id)
    before = cast(discord.Member, SimpleNamespace(id=200, guild=guild, premium_since=before_premium_since))
    after = cast(discord.Member, SimpleNamespace(id=200, guild=guild, premium_since=after_premium_since))

    await cog.on_member_update(before, after)

    assert service.members == []
