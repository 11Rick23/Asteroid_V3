from __future__ import annotations

import asyncio
import datetime
from datetime import datetime as dt
from logging import getLogger

import discord
from discord.ext import commands

from app.common.constants import AsteroidColor
from app.core.bot import AsteroidBot

from . import messages

logger = getLogger(__name__)


class BumpNotifier(commands.Cog):
    BUMP_AVAILABLE_DELTA = datetime.timedelta(hours=2)
    DISSOKU_UP_AVAILABLE_DELTA = datetime.timedelta(hours=2)
    DICOALL_UP_AVAILABLE_DELTA = datetime.timedelta(hours=1)

    def __init__(self, bot: AsteroidBot):
        self.bot = bot
        self.last_bump_notice_dt: dt | None = None
        self.last_dissoku_up_notice_dt: dt | None = None
        self.last_dicoall_up_notice_dt: dt | None = None

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if not self.bot.is_operating_guild(after.guild):
            return
        if after.interaction_metadata is None or not after.embeds:
            return
        first_embed = after.embeds[0]
        first_field = first_embed.fields[0] if first_embed.fields else None
        if (
            after.author.id == 761562078095867916
            and first_field is not None
            and "をアップしたよ" in (first_field.name or "")
            and before.flags.loading
        ):
            embed = discord.Embed(
                title=messages.thanks_title(
                    display_name=after.interaction_metadata.user.display_name,
                    service_name=messages.DISSOKU_THANKS_SERVICE,
                ),
                description=messages.next_notice_description(
                    relative_time=discord.utils.format_dt(
                        dt.now() + self.DISSOKU_UP_AVAILABLE_DELTA,
                        style="R",
                    ),
                    service_name=messages.UP_SERVICE,
                ),
                color=AsteroidColor.INFO,
            )
            if (
                self.last_dissoku_up_notice_dt is not None
                and (notice_dt := (dt.now() - self.last_dissoku_up_notice_dt).total_seconds()) <= 60
            ):
                embed.add_field(
                    name=messages.rta_title(service_name=messages.UP_SERVICE),
                    value=messages.rta_description(service_name=messages.UP_SERVICE, elapsed_seconds=notice_dt),
                )
            await after.reply(content=after.interaction_metadata.user.mention, embed=embed)
            logger.debug(
                "ディス速UPを検知しました: "
                f"guild_id={after.guild.id if after.guild is not None else None} "
                f"channel_id={after.channel.id} user_id={after.interaction_metadata.user.id} "
                f"next_notice_at={dt.now() + self.DISSOKU_UP_AVAILABLE_DELTA}"
            )
            await asyncio.sleep(self.DISSOKU_UP_AVAILABLE_DELTA.total_seconds())
            await after.channel.send(
                embed=discord.Embed(
                    title=messages.DISSOKU_REMINDER_TITLE,
                    description=messages.DISSOKU_REMINDER_DESCRIPTION,
                    color=AsteroidColor.INFO,
                )
            )
            self.last_dissoku_up_notice_dt = dt.now()
            logger.debug(
                "ディス速UP通知を送信しました: "
                f"guild_id={after.guild.id if after.guild is not None else None} channel_id={after.channel.id}"
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not self.bot.is_operating_guild(message.guild):
            return
        self.bot.remember_message(message)
        if message.interaction_metadata is None:
            return

        if (
            message.author.id == 903541413298450462
            and len(message.embeds) == 1
            and message.embeds[0].title
            and "サーバーがリストの最上段に更新されました！" in message.embeds[0].title
        ):
            embed = discord.Embed(
                title=messages.thanks_title(
                    display_name=message.interaction_metadata.user.display_name,
                    service_name=messages.DICOALL_THANKS_SERVICE,
                ),
                description=messages.next_notice_description(
                    relative_time=discord.utils.format_dt(
                        dt.now() + self.DICOALL_UP_AVAILABLE_DELTA,
                        style="R",
                    ),
                    service_name=messages.UP_SERVICE,
                ),
                color=AsteroidColor.INFO,
            )
            if (
                self.last_dicoall_up_notice_dt is not None
                and (notice_dt := (dt.now() - self.last_dicoall_up_notice_dt).total_seconds()) <= 60
            ):
                embed.add_field(
                    name=messages.rta_title(service_name=messages.UP_SERVICE),
                    value=messages.rta_description(service_name=messages.UP_SERVICE, elapsed_seconds=notice_dt),
                )
            await message.reply(content=message.interaction_metadata.user.mention, embed=embed)
            logger.debug(
                "Dicoall UPを検知しました: "
                f"guild_id={message.guild.id if message.guild is not None else None} "
                f"channel_id={message.channel.id} user_id={message.interaction_metadata.user.id} "
                f"next_notice_at={dt.now() + self.DICOALL_UP_AVAILABLE_DELTA}"
            )
            await asyncio.sleep(self.DICOALL_UP_AVAILABLE_DELTA.total_seconds())
            await message.channel.send(
                embed=discord.Embed(
                    title=messages.DICOALL_REMINDER_TITLE,
                    description=messages.DICOALL_REMINDER_DESCRIPTION,
                    color=AsteroidColor.INFO,
                )
            )
            self.last_dicoall_up_notice_dt = dt.now()
            logger.debug(
                "Dicoall UP通知を送信しました: "
                f"guild_id={message.guild.id if message.guild is not None else None} channel_id={message.channel.id}"
            )

        if (
            message.author.id == 302050872383242240
            and message.embeds
            and message.embeds[0].description
            and "表示順をアップしたよ" in message.embeds[0].description
        ):
            embed = discord.Embed(
                title=messages.thanks_title(
                    display_name=message.interaction_metadata.user.display_name,
                    service_name=messages.BUMP_THANKS_SERVICE,
                ),
                description=messages.next_notice_description(
                    relative_time=discord.utils.format_dt(dt.now() + self.BUMP_AVAILABLE_DELTA, style="R"),
                    service_name=messages.BUMP_THANKS_SERVICE,
                ),
                color=AsteroidColor.INFO,
            )
            if (
                self.last_bump_notice_dt is not None
                and (notice_dt := (dt.now() - self.last_bump_notice_dt).total_seconds()) <= 60
            ):
                embed.add_field(
                    name=messages.rta_title(service_name=messages.BUMP_SERVICE),
                    value=messages.rta_description(service_name=messages.BUMP_SERVICE, elapsed_seconds=notice_dt),
                )
            await message.reply(content=message.interaction_metadata.user.mention, embed=embed)
            logger.debug(
                "BUMPを検知しました: "
                f"guild_id={message.guild.id if message.guild is not None else None} "
                f"channel_id={message.channel.id} user_id={message.interaction_metadata.user.id} "
                f"next_notice_at={dt.now() + self.BUMP_AVAILABLE_DELTA}"
            )
            await asyncio.sleep(self.BUMP_AVAILABLE_DELTA.total_seconds())
            await message.channel.send(
                embed=discord.Embed(
                    title=messages.BUMP_REMINDER_TITLE,
                    description=messages.BUMP_REMINDER_DESCRIPTION,
                    color=AsteroidColor.INFO,
                )
            )
            self.last_bump_notice_dt = dt.now()
            logger.debug(
                "BUMP通知を送信しました: "
                f"guild_id={message.guild.id if message.guild is not None else None} channel_id={message.channel.id}"
            )


async def setup(bot: AsteroidBot) -> None:
    await bot.add_cog(BumpNotifier(bot))
