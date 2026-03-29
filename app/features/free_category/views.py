from __future__ import annotations

import discord

from app.common.constants import AsteroidColor
from app.common.utils import generate_timestamp

from .service import FreeCategoryService


class CreateChannelModal(discord.ui.Modal, title="チャンネルを作成"):
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

        embed = discord.Embed(
            color=interaction.user.color,
            title="新たなチャンネルが誕生しました…！",
            description=(
                f"{interaction.user.mention} が {new_channel.mention} を作成しました。"
                f" \n作成日時 : {generate_timestamp()}"
            ),
        )
        embed.set_footer(text="チャンネルを盛り上げよう！", icon_url=interaction.user.display_avatar.url)
        await new_channel.send(
            content=f"{interaction.user.mention} のフリーチャンネルです。",
            embed=embed,
        )
        await interaction.followup.send(f"{new_channel.mention} を作成しました！", ephemeral=True)


class CreateChannelButtonView(discord.ui.View):
    def __init__(self, service: FreeCategoryService):
        super().__init__(timeout=None)
        self.service = service

    @discord.ui.button(
        label="チャンネルを作成",
        style=discord.ButtonStyle.success,
        custom_id="fc_create_channel_button",
    )
    async def callback(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if self.service.is_creation_on_cooldown(interaction.user.id):
            cooldown_hours = self.service.get_creation_cooldown_seconds() / 3600
            await interaction.response.send_message(
                content=(
                    f"{interaction.user.mention}\n"
                    f"チャンネル作成には {cooldown_hours:g} 時間のクールダウンがあります。"
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(CreateChannelModal(self.service))


def build_creation_embed() -> discord.Embed:
    return discord.Embed(
        title="フリーカテゴリー内に新しいフリーチャンネルの作成",
        description="表示されるモーダルの指示に従って作成してください。",
        color=AsteroidColor.INFO,
    )


def build_help_embed() -> discord.Embed:
    return discord.Embed(
        title="フリーカテゴリー",
        description=(
            "`/fc archive`, `/fc edit`, `/fc block`, `/fc unblock`, `/fc op`, `/fc deop`, `/fc purge` を利用できます。"
            "\nチャンネル作成ボタンは `/setup free_category_button` で設置します。"
        ),
        color=AsteroidColor.INFO,
    )
