from __future__ import annotations

import discord
from discord import app_commands

ADMINISTRATOR_PERMISSIONS = discord.Permissions(administrator=True)


def admin_only[T](command: T) -> T:
    command = app_commands.default_permissions(ADMINISTRATOR_PERMISSIONS)(command)
    return app_commands.checks.has_permissions(administrator=True)(command)


def is_administrator(user: discord.abc.User) -> bool:
    return isinstance(user, discord.Member) and user.guild_permissions.administrator
