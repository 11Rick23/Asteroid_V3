from __future__ import annotations

import asyncio

import discord

from app.common.permissions import is_administrator

from . import messages
from .presentation import MigrationPreviewLayout, MigrationStatusView
from .service import MigrationPlan, MigrationService


class MigrationView(MigrationPreviewLayout):
    def __init__(self, service: MigrationService, source: discord.User, plan: MigrationPlan, actor_id: int) -> None:
        super().__init__(plan, actor_id)
        self.service = service
        self.source = source
        self.plan = plan
        self.actor_id = actor_id
        self.used = False
        self.lock = asyncio.Lock()
        self.confirm = discord.ui.Button(label=messages.CONFIRM, style=discord.ButtonStyle.danger)
        self.confirm.callback = self._confirm
        self.cancel = discord.ui.Button(label=messages.CANCEL, style=discord.ButtonStyle.secondary)
        self.cancel.callback = self._cancel
        self.add_item(discord.ui.ActionRow(self.confirm, self.cancel))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not await super().interaction_check(interaction):
            return False
        if interaction.user.id != self.actor_id or not is_administrator(interaction.user):
            await interaction.response.send_message(messages.UNAUTHORIZED, ephemeral=True)
            return False
        return True

    async def _confirm(self, interaction: discord.Interaction) -> None:
        if not await self.interaction_check(interaction):
            return
        await interaction.response.defer(ephemeral=False)
        async with self.lock:
            if self.used:
                await interaction.followup.send(messages.USED, ephemeral=True)
                return
            self.used = True
            self.stop()
            if (
                interaction.guild is None
                or not isinstance(interaction.channel, discord.TextChannel)
                or interaction.message is None
            ):
                await interaction.followup.send(messages.ERRORS["channel"], ephemeral=True)
                await self.show_status(interaction, messages.STOPPED)
                return
            try:
                result = await self.service.execute(
                    interaction.guild, self.source, self.plan, interaction.message, interaction.user.id
                )
            except ValueError as exc:
                result = messages.ERRORS.get(str(exc), messages.RANGE_ERROR)
                await self.show_status(interaction, messages.STOPPED)
            except Exception:
                await self.show_status(interaction, messages.STOPPED)
                raise
            if result != messages.COMPLETED:
                await interaction.followup.send(result, ephemeral=True)

    async def show_status(self, interaction: discord.Interaction, status: str) -> None:
        await interaction.edit_original_response(
            content=None,
            embed=None,
            view=MigrationStatusView(self.plan, self.actor_id, status, include_restore=True),
            attachments=[self.plan.detail_file()],
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def _cancel(self, interaction: discord.Interaction) -> None:
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
            await interaction.response.edit_message(
                content=None,
                embed=None,
                view=MigrationStatusView(self.plan, self.actor_id, messages.CANCELLED),
                attachments=[self.plan.detail_file()],
                allowed_mentions=discord.AllowedMentions.none(),
            )
