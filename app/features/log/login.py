from __future__ import annotations

import datetime
from logging import getLogger
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands

from app.common.constants import AsteroidColor
from app.common.discord_types import as_messageable
from app.core.bot import AsteroidBot

logger = getLogger(__name__)


class LogIn(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self.bot.wait_until_ready()
        log_channel_id = self.bot.config.log.main_log_channel_id
        if not log_channel_id:
            logger.warning("ログイン通知チャンネルが未設定です。")
            return

        log_channel = as_messageable(self.bot.get_channel(log_channel_id))
        if log_channel is None or self.bot.user is None:
            logger.warning(
                f"ログイン通知の送信先を解決できませんでした: "
                f"log_channel_id={log_channel_id} bot_user_ready={self.bot.user is not None}"
            )
            return

        now = datetime.datetime.now(ZoneInfo("Asia/Tokyo"))
        embed = discord.Embed(
            title="ログイン完了！",
            description=f"`{self.bot.user}`としてログインしました。",
            timestamp=now,
            color=AsteroidColor.SUCCESS,
            url=f"https://discord.com/developers/applications/{self.bot.application_id}/information",
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.add_field(name="ID", value=str(self.bot.user.id), inline=True)
        embed.add_field(
            name="作成日時 (JST)",
            value=str(self.bot.user.created_at.astimezone(ZoneInfo("Asia/Tokyo"))),
            inline=True,
        )
        await log_channel.send(embed=embed)
        logger.info(f"{self.bot.user} としてログインしました。")


async def setup(bot: AsteroidBot) -> None:
    await bot.add_cog(LogIn(bot))
