from __future__ import annotations

from datetime import datetime

import discord

from app.common.constants import AsteroidColor
from app.common.guild_scope import GuildScopedLayoutView, GuildScopedModal

from .service import FreeCategoryService


class CreateChannelModal(GuildScopedModal, title="チャンネルを作成"):
    channel_name = discord.ui.TextInput(label="チャンネル名", max_length=100)

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
        await interaction.followup.send(f"{new_channel.mention} を作成しました！", ephemeral=True)


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
                        "# 新たなチャンネルが誕生しました…！\n"
                        f"{creator.mention} のフリーチャンネルです。\n"
                        "チャンネルを盛り上げよう！\n"
                        f"\n-# 作成日時 : {discord.utils.format_dt(created_at, style='F')}"
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
            label="チャンネルを作成",
            style=discord.ButtonStyle.success,
            custom_id="fc_create_channel_button",
        )
        self.service = service

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.service.is_creation_on_cooldown(interaction.user.id):
            cooldown_hours = self.service.get_creation_cooldown_seconds() / 3600
            await interaction.response.send_message(
                content=(f"チャンネル作成には {cooldown_hours:g} 時間のクールダウンがあります。"),
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(CreateChannelModal(self.service))


class CreateChannelButtonView(GuildScopedLayoutView):
    def __init__(self, service: FreeCategoryService):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay("# 新しいフリーチャンネルの作成"),
                discord.ui.ActionRow(CreateChannelButton(service)),
                accent_color=AsteroidColor.INFO,
            )
        )
