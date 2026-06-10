from __future__ import annotations

import asyncio
from logging import getLogger

import discord
from discord.ext import commands

from app.common.command_groups import register_group, register_setup_command
from app.common.constants import AsteroidColor
from app.common.discord_types import as_text_channel
from app.core.bot import AsteroidBot

from .commands import setup_starboard, starboard_group

logger = getLogger(__name__)


class Starboard(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot
        self._locks: dict[int, asyncio.Lock] = {}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        self.bot.remember_message(message)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, event: discord.RawReactionActionEvent) -> None:
        if event.member is None or event.member.bot or event.guild_id is None or str(event.emoji) != "⭐":
            return
        channel = as_text_channel(self.bot.get_channel(event.channel_id))
        if channel is None:
            logger.warning(f"スターボード対象チャンネルが見つかりませんでした: channel_id={event.channel_id}")
            return
        message = self.bot.get_message(event.message_id) or await channel.fetch_message(event.message_id)
        if message.author.id == event.member.id:
            return

        given_star_data = await self.bot.db.given_stars.get_given_star(event.member.id)
        if given_star_data is None:
            await self.bot.db.given_stars.create_given_star(event.member.id)
        else:
            await self.bot.db.given_stars.add_given_star(event.member.id)

        reactions = next((reaction for reaction in message.reactions if str(reaction.emoji) == "⭐"), None)
        if reactions is None:
            return
        users = [user async for user in reactions.users() if not user.bot and user.id != message.author.id]
        star_amount = len(users)
        if star_amount < 5:
            return
        logger.debug(
            f"スターボード更新条件を満たしました: guild_id={event.guild_id} "
            f"message_id={message.id} star_amount={star_amount}"
        )
        await self.update_starboard(message, star_amount)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, event: discord.RawReactionActionEvent) -> None:
        if event.guild_id is None or str(event.emoji) != "⭐":
            return
        guild = self.bot.get_guild(event.guild_id)
        if guild is None:
            logger.warning(f"スターボード対象ギルドが見つかりませんでした: guild_id={event.guild_id}")
            return
        channel = as_text_channel(guild.get_channel(event.channel_id))
        if channel is None:
            logger.warning(f"スターボード対象チャンネルが見つかりませんでした: channel_id={event.channel_id}")
            return
        message = self.bot.get_message(event.message_id) or await channel.fetch_message(event.message_id)
        if message.author.id == event.user_id:
            return

        given_star_data = await self.bot.db.given_stars.get_given_star(event.user_id)
        if given_star_data is not None:
            await self.bot.db.given_stars.remove_given_star(event.user_id)

        star_amount = 0
        reaction = next((reaction for reaction in message.reactions if str(reaction.emoji) == "⭐"), None)
        if reaction is not None:
            users = [user async for user in reaction.users() if not user.bot and user.id != message.author.id]
            star_amount = len(users)

        lock = self._locks.setdefault(message.id, asyncio.Lock())
        async with lock:
            starred_message_data = await self.bot.db.starred_messages.get_starred_message(message.id)
            if starred_message_data is None:
                return

            starboard_channel = as_text_channel(self.bot.get_channel(self.bot.config.starboard.starboard_channel_id))
            if starboard_channel is None:
                logger.warning("スターボードチャンネルが未設定または未解決です。")
                return
            starboard_message = self.bot.get_message(starred_message_data.starboard_message_id)
            if starboard_message is None:
                starboard_message = await starboard_channel.fetch_message(starred_message_data.starboard_message_id)

            if star_amount < 5:
                await starboard_message.delete()
                await self.bot.db.starred_messages.delete_starred_message(message.id)
                logger.debug(
                    f"スターボード投稿を削除しました: guild_id={guild.id} "
                    f"message_id={message.id} starboard_message_id={starboard_message.id}"
                )
                return

            starboard_content, starboard_embed = await self._build_starboard(message, star_amount)
            starboard_embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
            starboard_embed.add_field(name="元のメッセージ", value=f"[リンク]({message.jump_url})", inline=False)
            starboard_embed.set_footer(text=str(message.id))
            await starboard_message.edit(content=starboard_content, embed=starboard_embed)
            await self.bot.db.starred_messages.set_star_amount(message.id, star_amount)
            logger.debug(
                f"スターボード投稿を更新しました: guild_id={guild.id} "
                f"message_id={message.id} starboard_message_id={starboard_message.id} star_amount={star_amount}"
            )

    async def update_starboard(self, starred_message: discord.Message, star_amount: int) -> None:
        starboard_channel = as_text_channel(self.bot.get_channel(self.bot.config.starboard.starboard_channel_id))
        if starboard_channel is None:
            logger.warning("スターボードチャンネルが未設定または未解決です。")
            return

        starboard_content, starboard_embed = await self._build_starboard(starred_message, star_amount)
        starboard_embed.set_author(
            name=starred_message.author.display_name, icon_url=starred_message.author.display_avatar.url
        )
        starboard_embed.add_field(name="元のメッセージ", value=f"[リンク]({starred_message.jump_url})", inline=False)
        starboard_embed.set_footer(text=str(starred_message.id))

        lock = self._locks.setdefault(starred_message.id, asyncio.Lock())
        async with lock:
            starred_message_data = await self.bot.db.starred_messages.get_starred_message(starred_message.id)
            if starred_message_data is None:
                first_starboard_message = await starboard_channel.send(
                    content=starboard_content, embed=starboard_embed
                )
                await self.bot.db.starred_messages.create_starred_message(
                    starred_message.id,
                    first_starboard_message.id,
                    star_amount,
                    starred_message.author.id,
                    starred_message.channel.id,
                )
                logger.debug(
                    "スターボード投稿を作成しました: guild_id="
                    f"{starred_message.guild.id if starred_message.guild else None} "
                    f"message_id={starred_message.id} starboard_message_id={first_starboard_message.id} "
                    f"star_amount={star_amount}"
                )
                return

            starboard_message = self.bot.get_message(starred_message_data.starboard_message_id)
            if starboard_message is None:
                starboard_message = await starboard_channel.fetch_message(starred_message_data.starboard_message_id)
            await starboard_message.edit(content=starboard_content, embed=starboard_embed)
            await self.bot.db.starred_messages.set_star_amount(starred_message.id, star_amount)
            logger.debug(
                "スターボード投稿を更新しました: guild_id="
                f"{starred_message.guild.id if starred_message.guild else None} "
                f"message_id={starred_message.id} starboard_message_id={starboard_message.id} "
                f"star_amount={star_amount}"
            )

    async def _build_starboard(self, starred_message: discord.Message, star_amount: int) -> tuple[str, discord.Embed]:
        images: list[str] = []
        files: list[str] = []
        embed = discord.Embed(
            color=AsteroidColor.YELLOW if star_amount <= 10 else AsteroidColor.CYAN,
            description=starred_message.content or None,
            timestamp=starred_message.created_at,
        )
        for attachment in starred_message.attachments:
            if attachment.filename.endswith((".jpeg", ".jpg", ".png", ".gif", ".apng", ".tiff", ".bmp", ".webp")):
                images.append(attachment.url)
            else:
                files.append(attachment.url)
        if images:
            embed.set_image(url=images[0])
        if files:
            embed.add_field(name="添付ファイル", value="\n".join(files))
        channel_mention = getattr(starred_message.channel, "mention", None)
        if not isinstance(channel_mention, str):
            channel_mention = f"<#{starred_message.channel.id}>"
        return f"{self.get_star_emoji(star_amount)} **{star_amount}** {channel_mention}", embed

    def get_star_emoji(self, star_amount: int) -> str:
        return "🌟" if star_amount < 10 else "💫"

    def int_to_emoji(self, num: int) -> str:
        return ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"][num]


async def setup(bot: AsteroidBot) -> None:
    register_setup_command(bot, setup_starboard)
    register_group(bot, starboard_group)
    await bot.add_cog(Starboard(bot))
