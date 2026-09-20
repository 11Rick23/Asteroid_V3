from __future__ import annotations

import asyncio

import discord

from app.common.guild_scope import GuildScopedView
from app.common.permissions import is_administrator

from . import messages
from .service import MigrationPlan, MigrationService


class MigrationView(GuildScopedView):
    def __init__(self, service: MigrationService, source: discord.User, plan: MigrationPlan, actor_id: int) -> None:
        super().__init__(timeout=300)
        self.service = service
        self.source = source
        self.plan = plan
        self.actor_id = actor_id
        self.used = False
        self.lock = asyncio.Lock()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not await super().interaction_check(interaction):
            return False
        if interaction.user.id != self.actor_id or not is_administrator(interaction.user):
            await interaction.response.send_message(messages.UNAUTHORIZED, ephemeral=True)
            return False
        return True

    @discord.ui.button(label=messages.CONFIRM, style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self.interaction_check(interaction):
            return
        await interaction.response.defer(ephemeral=False)
        async with self.lock:
            if self.used:
                await interaction.followup.send(messages.USED, ephemeral=True)
                return
            self.used = True
            self.stop()
            if interaction.guild is None or not isinstance(interaction.channel, discord.TextChannel):
                await interaction.followup.send(messages.ERRORS["channel"], ephemeral=True)
                await interaction.edit_original_response(view=None)
                return
            try:
                result = await self.service.execute(
                    interaction.guild, self.source, self.plan, interaction.channel, interaction.user.id
                )
            except ValueError as exc:
                result = messages.ERRORS.get(str(exc), messages.RANGE_ERROR)
            if result == messages.COMPLETED:
                await interaction.edit_original_response(content=result, view=None)
            else:
                await interaction.followup.send(result, ephemeral=True)
                await interaction.edit_original_response(view=None)

    @discord.ui.button(label=messages.CANCEL, style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self.interaction_check(interaction):
            return
        if self.used:
            await interaction.response.send_message(messages.USED, ephemeral=True)
            return
        async with self.lock:
            if self.used:
                await interaction.response.send_message(messages.USED, ephemeral=True)
                return
            self.used = True
            self.stop()
            await interaction.response.edit_message(content=messages.CANCELLED, view=None)
