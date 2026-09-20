from __future__ import annotations

import discord
from discord import app_commands

from app.common.command_groups import get_bot, register_command
from app.common.permissions import admin_only
from app.core.bot import AsteroidBot
from app.database.account_migration import MigrationOptions

from . import messages
from .presentation import preview_embed
from .service import MigrationService
from .views import MigrationView


@app_commands.command(name="migrate", description=messages.COMMAND_DESCRIPTION)
@app_commands.guild_only()
@app_commands.rename(
    source=messages.SOURCE_LABEL,
    target=messages.TARGET_LABEL,
    leveling=messages.LEVELING_LABEL,
    roles=messages.ROLES_LABEL,
    birthday=messages.BIRTHDAY_LABEL,
    free_category=messages.FC_LABEL,
)
@app_commands.describe(
    source=messages.SOURCE_DESCRIPTION,
    target=messages.TARGET_DESCRIPTION,
    leveling=messages.LEVELING_DESCRIPTION,
    roles=messages.ROLES_DESCRIPTION,
    birthday=messages.BIRTHDAY_DESCRIPTION,
    free_category=messages.FC_DESCRIPTION,
)
@admin_only
async def migrate(
    interaction: discord.Interaction,
    source: discord.User,
    target: discord.Member,
    leveling: bool = True,
    roles: bool = True,
    birthday: bool = True,
    free_category: bool = True,
) -> None:
    if interaction.guild is None or not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message(messages.ERRORS["channel"], ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    service = MigrationService(get_bot(interaction))
    try:
        plan = await service.preview(
            interaction.guild, source, target.id, MigrationOptions(leveling, roles, birthday, free_category)
        )
    except ValueError as exc:
        await interaction.followup.send(messages.ERRORS.get(str(exc), messages.RANGE_ERROR), ephemeral=True)
        return
    await interaction.channel.send(
        embed=preview_embed(plan),
        file=plan.detail_file(),
        view=MigrationView(service, source, plan, interaction.user.id),
        allowed_mentions=discord.AllowedMentions.none(),
    )
    await interaction.delete_original_response()


async def setup(bot: AsteroidBot) -> None:
    register_command(bot, migrate)
