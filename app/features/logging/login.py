from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands

from app.common.constants import AsteroidColor
from app.core.bot import AsteroidBot


class LogIn(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        await self.bot.wait_until_ready()
        log_channel_id = self.bot.config.log.main_log_channel_id
        if not log_channel_id:
            return

        log_channel = self.bot.get_channel(log_channel_id)
        if log_channel is None or self.bot.user is None:
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
            name="Creation Date (JST)",
            value=str(self.bot.user.created_at.astimezone(ZoneInfo("Asia/Tokyo"))),
            inline=True,
        )
        await log_channel.send(embed=embed)


async def setup(bot: AsteroidBot) -> None:
    await bot.add_cog(LogIn(bot))
