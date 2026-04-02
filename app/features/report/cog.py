from __future__ import annotations

from logging import getLogger

import discord
from discord import app_commands
from discord.ext import commands

from app.core.bot import AsteroidBot
from app.features.report.service import build_report_embed
from app.features.report.views import ReportResolveView

logger = getLogger(__name__)


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
        logger.debug(
            "レポート送信を受け付けました: "
            f"guild_id={interaction.guild.id if interaction.guild is not None else None} "
            f"channel_id={interaction.channel_id} "
            f"reporter_id={interaction.user.id if interaction.user is not None else None} "
            f"violator_id={violator.id} has_image={image is not None}"
        )
        await interaction.response.send_message(content="レポート送信中…", ephemeral=True)
        if interaction.guild is None:
            logger.warning(f"レポート送信を中断しました: guild_id=None reporter_id={interaction.user.id}")
            await interaction.edit_original_response(content="サーバー内でのみ使用できます。")
            return

        report_receive_channel = interaction.guild.get_channel(self.bot.config.report.report_receive_channel_id)
        if report_receive_channel is None:
            logger.warning(
                "レポート送信先チャンネルが見つかりませんでした: "
                f"guild_id={interaction.guild.id} reporter_id={interaction.user.id} "
                f"channel_id={self.bot.config.report.report_receive_channel_id}"
            )
            await interaction.edit_original_response(content="レポート送信先チャンネルが見つかりませんでした。")
            return

        embed = build_report_embed(interaction.user, content, image)
        ping_role_id = self.bot.config.report.report_ping_role_id
        prefix = f"<@&{ping_role_id}>\n" if ping_role_id else ""
        await report_receive_channel.send(
            content=f"{prefix}レポートされたユーザー: {violator.mention}",
            embed=embed,
            view=ReportResolveView(),
        )
        logger.debug(
            "レポート送信が完了しました: "
            f"guild_id={interaction.guild.id} reporter_id={interaction.user.id} "
            f"violator_id={violator.id} destination_channel_id={report_receive_channel.id}"
        )
        await interaction.edit_original_response(content="レポート送信完了。\nレポートありがとうございました。")


async def setup(bot: AsteroidBot) -> None:
    await bot.add_cog(ReportCog(bot))
