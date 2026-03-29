from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from app.core.bot import AsteroidBot
from app.features.moderation.service import build_report_embed
from app.features.moderation.views import ReportResolveView


class ReportCog(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.add_view(ReportResolveView())

    @app_commands.command(name="report", description="レポートを送信")
    @app_commands.describe(
        violator="レポートするユーザー",
        content="違反した内容を詳しく書いて下さい。",
        image="違反内容の画像などがあれば添付して下さい。",
    )
    @app_commands.guild_only()
    async def report(
        self,
        interaction: discord.Interaction,
        violator: discord.User,
        content: str,
        image: discord.Attachment | None = None,
    ) -> None:
        await interaction.response.send_message(content="レポート送信中…", ephemeral=True)
        if interaction.guild is None:
            await interaction.edit_original_response(content="サーバー内でのみ使用できます。")
            return

        report_receive_channel = interaction.guild.get_channel(self.bot.config.moderation.report_receive_channel_id)
        if report_receive_channel is None:
            await interaction.edit_original_response(content="レポート送信先チャンネルが見つかりませんでした。")
            return

        embed = build_report_embed(interaction.user, content, image)
        await report_receive_channel.send(
            content="<@&773884309374500884>\nレポートされたユーザー: " + violator.mention,
            embed=embed,
            view=ReportResolveView(),
        )
        await interaction.edit_original_response(content="レポート送信完了。\nレポートありがとうございました。")


async def setup(bot: AsteroidBot) -> None:
    await bot.add_cog(ReportCog(bot))
