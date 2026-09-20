from __future__ import annotations

from datetime import datetime

import discord

from app.common.constants import AsteroidColor
from app.common.guild_scope import GuildScopedLayoutView, GuildScopedModal

from . import messages
from .service import FreeCategoryService


class CreateChannelModal(GuildScopedModal, title=messages.CREATE_MODAL_TITLE):
    channel_name = discord.ui.TextInput(label=messages.CHANNEL_NAME_LABEL, max_length=100)

    def __init__(self, service: FreeCategoryService):
        super().__init__(timeout=None)
        self.service = service

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            new_channel = await self.service.create_channel(interaction, self.channel_name.value)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        await new_channel.send(
            view=CreatedChannelView(
                interaction.user,
                new_channel,
                created_at=new_channel.created_at,
            )
        )
        await interaction.followup.send(messages.channel_created(channel_mention=new_channel.mention), ephemeral=True)


class CreatedChannelView(GuildScopedLayoutView):
    def __init__(
        self,
        creator: discord.User | discord.Member,
        channel: discord.TextChannel,
        *,
        created_at: datetime,
    ) -> None:
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Container(
                discord.ui.Section(
                    discord.ui.TextDisplay(
                        messages.created_channel_content(
                            creator_mention=creator.mention,
                            created_at=discord.utils.format_dt(created_at, style="F"),
                        )
                    ),
                    accessory=discord.ui.Thumbnail(
                        str(creator.display_avatar.url),
                    ),
                ),
                accent_color=creator.color,
            )
        )


class CreateChannelButton(discord.ui.Button["CreateChannelButtonView"]):
    def __init__(self, service: FreeCategoryService):
        super().__init__(
            label=messages.CREATE_BUTTON_LABEL,
            style=discord.ButtonStyle.success,
            custom_id="fc_create_channel_button",
        )
        self.service = service

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.service.is_creation_on_cooldown(interaction.user.id):
            cooldown_hours = self.service.get_creation_cooldown_seconds() / 3600
            await interaction.response.send_message(
                content=messages.create_cooldown(cooldown_hours=cooldown_hours),
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(CreateChannelModal(self.service))


class CreateChannelButtonView(GuildScopedLayoutView):
    def __init__(self, service: FreeCategoryService):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(messages.CREATE_PANEL_TITLE),
                discord.ui.ActionRow(CreateChannelButton(service)),
                accent_color=AsteroidColor.INFO,
            )
        )
