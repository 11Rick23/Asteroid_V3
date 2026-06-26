from __future__ import annotations

import re
from logging import getLogger

import discord
from discord.ext import commands

from app.common.constants import AsteroidColor
from app.common.discord_types import as_text_channel
from app.core.bot import AsteroidBot

logger = getLogger(__name__)

discord_message_url_pattern = re.compile(
    r"(?<!<)https://(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/"
    r"(?P<guild>[0-9]{17,20})/(?P<channel>[0-9]{17,20})/(?P<message>[0-9]{17,20})(?![0-9>])"
)

IMAGE_FILE_EXTENSION = (".jpeg", ".jpg", ".png", ".gif", ".apng", ".tiff", ".bmp", ".webp")


class LinkExpander(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot

    @commands.Cog.listener("on_message")
    async def link_expander(self, message: discord.Message) -> None:
        guild = message.guild
        if message.author.bot or guild is None or not self.bot.is_operating_guild(guild):
            return
        self.bot.remember_message(message)

        urls = [i.group("channel", "message") for i in re.finditer(discord_message_url_pattern, message.content)]
        if not urls:
            return

        referenced_messages: list[discord.Message] = []
        for channel_id, message_id in urls:
            channel = as_text_channel(self.bot.get_channel(int(channel_id)))
            if channel is None or not self.bot.is_operating_channel(channel):
                logger.debug(f"リンク展開対象チャンネルが見つかりませんでした: channel_id={channel_id}")
                continue
            try:
                fetched_message = await channel.fetch_message(int(message_id))
            except discord.NotFound:
                logger.debug(
                    f"リンク展開対象メッセージが見つかりませんでした: channel_id={channel_id} message_id={message_id}"
                )
                continue
            if fetched_message not in referenced_messages:
                referenced_messages.append(fetched_message)

        for referenced_message in referenced_messages:
            allow_nsfw = isinstance(message.channel, discord.TextChannel) and message.channel.is_nsfw()
            embeds = self.generate_embed(referenced_message, allow_nsfw)
            await message.reply(content=None, embeds=embeds, mention_author=False)
        if referenced_messages:
            logger.debug(
                f"リンク展開を実行しました: guild_id={guild.id} "
                f"channel_id={message.channel.id} count={len(referenced_messages)}"
            )

    def generate_embed(self, message: discord.Message, allow_nsfw: bool) -> list[discord.Embed]:
        is_nsfw = isinstance(message.channel, discord.TextChannel) and message.channel.is_nsfw()
        if is_nsfw and not allow_nsfw:
            embed = discord.Embed(
                description="NSFWメッセージのため非表示\nリンク先の添付ファイルなどに気を付けて参照してください。",
                color=AsteroidColor.INFO,
                timestamp=message.created_at,
            )
        else:
            embed = discord.Embed(description=message.content, color=AsteroidColor.INFO, timestamp=message.created_at)

        embed.set_author(
            name=message.author.display_name, url=message.jump_url, icon_url=message.author.display_avatar.url
        )
        channel_name = message.channel.name if isinstance(message.channel, discord.abc.GuildChannel) else "unknown"
        if message.guild and message.guild.icon:
            embed.set_footer(text=channel_name, icon_url=message.guild.icon.url)
        else:
            embed.set_footer(text=channel_name)

        if is_nsfw and not allow_nsfw:
            return [embed]

        banner_image = None
        extra_files = ""
        for attachment in message.attachments:
            if attachment.filename.lower().endswith(IMAGE_FILE_EXTENSION) and not banner_image:
                banner_image = attachment.url
            file_name = f"[{attachment.filename}]({attachment.url})\n"
            if len(extra_files + file_name) >= 1024:
                extra_files += "\n..."
                break
            extra_files += file_name
        if banner_image:
            embed.set_image(url=banner_image)
        if extra_files:
            embed.add_field(name="ファイル", value=extra_files)

        embed_list = [] if not message.content and not message.attachments else [embed]
        embed_list.extend(message.embeds)
        return embed_list


async def setup(bot: AsteroidBot) -> None:
    await bot.add_cog(LinkExpander(bot))
