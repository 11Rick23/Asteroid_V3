from __future__ import annotations

from typing import Any

import discord
from discord import app_commands

from app.common.interaction_errors import handle_ui_error

OUTSIDE_OPERATING_GUILD_MESSAGE = "このBOTはこのサーバーでは利用できません。"


def get_operating_guild_id(client: Any) -> int:
    return int(client.config.discord.guild_id)


def is_operating_guild_id(client: Any, guild_id: int | None) -> bool:
    return guild_id is not None and guild_id == get_operating_guild_id(client)


def is_operating_guild(client: Any, guild: discord.Guild | None) -> bool:
    return guild is not None and is_operating_guild_id(client, guild.id)


async def send_outside_operating_guild_message(interaction: discord.Interaction) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(OUTSIDE_OPERATING_GUILD_MESSAGE, ephemeral=True)
        return
    await interaction.response.send_message(OUTSIDE_OPERATING_GUILD_MESSAGE, ephemeral=True)


class OutsideOperatingGuild(app_commands.CheckFailure):
    pass


class OperatingGuildCommandTree(app_commands.CommandTree[Any]):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if is_operating_guild_id(self.client, interaction.guild_id):
            return True
        raise OutsideOperatingGuild


class GuildScopedView(discord.ui.View):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if is_operating_guild_id(interaction.client, interaction.guild_id):
            return True
        await send_outside_operating_guild_message(interaction)
        return False

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
    ) -> None:
        await handle_ui_error(interaction, error)


class GuildScopedLayoutView(discord.ui.LayoutView):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if is_operating_guild_id(interaction.client, interaction.guild_id):
            return True
        await send_outside_operating_guild_message(interaction)
        return False

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
    ) -> None:
        await handle_ui_error(interaction, error)


class GuildScopedModal(discord.ui.Modal):
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if is_operating_guild_id(interaction.client, interaction.guild_id):
            return True
        await send_outside_operating_guild_message(interaction)
        return False

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ) -> None:
        await handle_ui_error(interaction, error)
