from __future__ import annotations

import asyncio
import datetime
from datetime import datetime as dt

import discord
from discord.ext import commands

from app.common.constants import AsteroidColor
from app.core.bot import AsteroidBot


class BumpNotifier(commands.Cog):
    BUMP_AVAILABLE_DELTA = datetime.timedelta(hours=2)
    UP_AVAILABLE_DELTA = datetime.timedelta(hours=1)

    def __init__(self, bot: AsteroidBot):
        self.bot = bot
        self.last_bump_notice_dt: dt | None = None
        self.last_dissoku_up_notice_dt: dt | None = None
        self.last_dicoall_up_notice_dt: dt | None = None

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if after.interaction_metadata is None or not after.embeds:
            return
        if (
            after.author.id == 761562078095867916
            and "をアップしたよ!" in after.embeds[0].fields[0].name
            and before.flags.loading
        ):
            embed = discord.Embed(
                title=f"{after.interaction_metadata.user.display_name}さん、ディス速のUPありがとう！",
                description=(
                    f"{discord.utils.format_dt(dt.now() + self.BUMP_AVAILABLE_DELTA, style='R')}"
                    "にこのチャンネルでUP通知を行います"
                ),
                color=AsteroidColor.INFO,
            )
            if (
                self.last_dissoku_up_notice_dt is not None
                and (notice_dt := (dt.now() - self.last_dissoku_up_notice_dt).total_seconds()) <= 60
            ):
                embed.add_field(name="UP RTAが行われました！", value=f"UP通知から{notice_dt}秒でUPが行われました")
            await after.reply(content=after.interaction_metadata.user.mention, embed=embed)
            await asyncio.sleep(self.BUMP_AVAILABLE_DELTA.total_seconds())
            await after.channel.send(
                embed=discord.Embed(
                    title="前回のディス速のUPから2時間経過しました！",
                    description="</up:1363739182672904354>を実行しよう！",
                    color=AsteroidColor.INFO,
                )
            )
            self.last_dissoku_up_notice_dt = dt.now()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        self.bot.remember_message(message)
        if message.interaction_metadata is None:
            return

        if (
            message.author.id == 903541413298450462
            and len(message.embeds) == 1
            and message.embeds[0].description
            and "**サーバーが上部に表示されました。**" in message.embeds[0].description
        ):
            embed = discord.Embed(
                title=f"{message.interaction_metadata.user.display_name}さん、DicoallのUPありがとう！",
                description=(
                    f"{discord.utils.format_dt(dt.now() + self.UP_AVAILABLE_DELTA, style='R')}"
                    "にこのチャンネルでUP通知を行います"
                ),
                color=AsteroidColor.INFO,
            )
            if (
                self.last_dicoall_up_notice_dt is not None
                and (notice_dt := (dt.now() - self.last_dicoall_up_notice_dt).total_seconds()) <= 60
            ):
                embed.add_field(name="UP RTAが行われました！", value=f"UP通知から{notice_dt}秒でUPが行われました")
            await message.reply(content=message.interaction_metadata.user.mention, embed=embed)
            await asyncio.sleep(self.UP_AVAILABLE_DELTA.total_seconds())
            await message.channel.send(
                embed=discord.Embed(
                    title="前回のDicoallのUPから1時間経過しました！",
                    description="</up:935190259111706754>を実行しよう！",
                    color=AsteroidColor.INFO,
                )
            )
            self.last_dicoall_up_notice_dt = dt.now()

        if (
            message.author.id == 302050872383242240
            and message.embeds
            and message.embeds[0].description
            and "表示順をアップしたよ" in message.embeds[0].description
        ):
            embed = discord.Embed(
                title=f"{message.interaction_metadata.user.display_name}さん、Bumpありがとう！",
                description=(
                    f"{discord.utils.format_dt(dt.now() + self.BUMP_AVAILABLE_DELTA, style='R')}"
                    "にこのチャンネルでBump通知を行います"
                ),
                color=AsteroidColor.INFO,
            )
            if (
                self.last_bump_notice_dt is not None
                and (notice_dt := (dt.now() - self.last_bump_notice_dt).total_seconds()) <= 60
            ):
                embed.add_field(
                    name="BUMP RTAが行われました！", value=f"BUMP通知から{notice_dt}秒でBUMPが行われました"
                )
            await message.reply(content=message.interaction_metadata.user.mention, embed=embed)
            await asyncio.sleep(self.BUMP_AVAILABLE_DELTA.total_seconds())
            await message.channel.send(
                embed=discord.Embed(
                    title="前回のBumpから2時間経過しました！",
                    description="</bump:947088344167366698>を実行しよう！",
                    color=AsteroidColor.INFO,
                )
            )
            self.last_bump_notice_dt = dt.now()


async def setup(bot: AsteroidBot) -> None:
    await bot.add_cog(BumpNotifier(bot))
