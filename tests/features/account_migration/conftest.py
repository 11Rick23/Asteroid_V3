from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from app.core.bot import AsteroidBot
from app.core.config import AsteroidConfig, DiscordConfig, FreeCategoryConfig
from app.features.account_migration.service import MigrationService
from tests.support.sqlite_database import SQLiteDatabase


@pytest.fixture
def world():
    """Discordのロール・個別権限の変更をメモリ内に反映する。"""
    roles = {role_id: Mock(spec=discord.Role, id=role_id) for role_id in (10, 20, 30)}
    for role in roles.values():
        role.managed = False
        role.is_default.return_value = False
        role.is_assignable.return_value = True

    def member(user_id, role_ids):
        value = Mock(spec=discord.Member, id=user_id, bot=False)
        value.roles = [roles[role_id] for role_id in role_ids]
        value.guild_permissions = discord.Permissions(administrator=True)

        async def add_roles(*new, **kwargs):
            value.roles = list(set(value.roles) | set(new))

        async def remove_roles(*removed, **kwargs):
            value.roles = [role for role in value.roles if role not in removed]

        value.add_roles = AsyncMock(side_effect=add_roles)
        value.remove_roles = AsyncMock(side_effect=remove_roles)
        return value

    source, target = member(1, [10, 20]), member(2, [20, 30])
    guild = Mock(spec=discord.Guild, id=100)
    guild.get_role.side_effect = roles.get
    guild.fetch_member = AsyncMock(side_effect=lambda user_id: {1: source, 2: target}[user_id])
    guild.me.guild_permissions = discord.Permissions(manage_roles=True)
    channel = Mock(spec=discord.TextChannel, id=500, category_id=400, guild=guild)
    channel.overwrites = {
        source: discord.PermissionOverwrite(view_channel=True),
        target: discord.PermissionOverwrite(send_messages=False),
    }
    channel.permissions_for.return_value = discord.Permissions(manage_roles=True)

    async def set_permissions(user, overwrite, **kwargs):
        if overwrite is None:
            channel.overwrites.pop(user, None)
        else:
            channel.overwrites[user] = overwrite

    channel.set_permissions = AsyncMock(side_effect=set_permissions)
    record = Mock(id=600, edit=AsyncMock())
    channel.send = AsyncMock(return_value=record)
    guild.fetch_channels = AsyncMock(return_value=[channel])
    bot = SimpleNamespace(
        db=SQLiteDatabase(),
        config=AsteroidConfig(
            discord=DiscordConfig(guild_id=100), free_category=FreeCategoryConfig(free_category_id=400)
        ),
        is_operating_guild=lambda value: value.id == 100,
    )
    return SimpleNamespace(
        bot=bot,
        service=MigrationService(cast(AsteroidBot, bot)),
        source=source,
        target=target,
        guild=guild,
        channel=channel,
        roles=roles,
        record=record,
    )
