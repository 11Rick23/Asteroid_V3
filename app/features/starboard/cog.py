from __future__ import annotations

import asyncio
from asyncio import sleep
from re import findall

import discord
from discord import app_commands
from discord.ext import commands

from app.common.command_groups import get_bot, register_group, register_setup_command
from app.common.constants import AsteroidColor
from app.common.pages import Paginator
from app.core.bot import AsteroidBot

starboard_group = app_commands.Group(name="starboard", description="スターボード関連のコマンド")


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
        channel = self.bot.get_channel(event.channel_id)
        if channel is None:
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
        await self.update_starboard(message, star_amount)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, event: discord.RawReactionActionEvent) -> None:
        if event.guild_id is None or str(event.emoji) != "⭐":
            return
        guild = self.bot.get_guild(event.guild_id)
        if guild is None:
            return
        channel = guild.get_channel(event.channel_id)
        if channel is None:
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

            starboard_channel = self.bot.get_channel(self.bot.config["starboard_channel_id"])
            if starboard_channel is None:
                return
            starboard_message = self.bot.get_message(starred_message_data.starboard_message_id)
            if starboard_message is None:
                starboard_message = await starboard_channel.fetch_message(starred_message_data.starboard_message_id)

            if star_amount < 5:
                await starboard_message.delete()
                await self.bot.db.starred_messages.delete_starred_message(message.id)
                return

            starboard_content, starboard_embed = await self._build_starboard(message, star_amount)
            starboard_embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
            starboard_embed.add_field(name="元のメッセージ", value=f"[リンク]({message.jump_url})", inline=False)
            starboard_embed.set_footer(text=str(message.id))
            await starboard_message.edit(content=starboard_content, embed=starboard_embed)
            await self.bot.db.starred_messages.set_star_amount(message.id, star_amount)

    async def update_starboard(self, starred_message: discord.Message, star_amount: int) -> None:
        starboard_channel = self.bot.get_channel(self.bot.config["starboard_channel_id"])
        if starboard_channel is None:
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
                return

            starboard_message = self.bot.get_message(starred_message_data.starboard_message_id)
            if starboard_message is None:
                starboard_message = await starboard_channel.fetch_message(starred_message_data.starboard_message_id)
            await starboard_message.edit(content=starboard_content, embed=starboard_embed)
            await self.bot.db.starred_messages.set_star_amount(starred_message.id, star_amount)

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
            embed.add_field(name="Attachments", value="\n".join(files))
        return f"{self.get_star_emoji(star_amount)} **{star_amount}** {starred_message.channel.mention}", embed

    def get_star_emoji(self, star_amount: int) -> str:
        return "🌟" if star_amount < 10 else "💫"

    def int_to_emoji(self, num: int) -> str:
        return ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"][num]


@app_commands.command(name="starboard", description="Carl-botからの移行")
async def migrate_starboard(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    await interaction.response.defer()

    old_starboard_channel = bot.get_channel(802172341546123286)
    new_starboard_channel = bot.get_channel(bot.config["starboard_channel_id"])
    if old_starboard_channel is None or new_starboard_channel is None:
        await interaction.followup.send("スターボードチャンネル設定が不足しています。", ephemeral=True)
        return

    cog = next((c for c in bot.cogs.values() if isinstance(c, Starboard)), None)
    if cog is None:
        await interaction.followup.send("Starboard cog が読み込まれていません。", ephemeral=True)
        return

    async for message in old_starboard_channel.history(limit=None, oldest_first=True):
        if message.author.id != 235148962103951360:
            continue

        starred_message_data = message.embeds[0].fields[0].value.replace("[Jump!](", "").rsplit(")")[0].split("/")
        try:
            source_channel = bot.get_channel(int(starred_message_data[-2]))
            starred_message = await source_channel.fetch_message(int(starred_message_data[-1]))
        except discord.Forbidden:
            continue
        except Exception:
            extracted_star_amount = int(findall(r"\d+", message.content)[0])
            new_embed_dict = message.embeds[0].to_dict()
            new_embed_dict["fields"][0]["name"] = "元のメッセージ"
            new_embed_dict["fields"][0]["value"] = f"[リンク]({message.jump_url})"
            starboard_message = await new_starboard_channel.send(
                content=message.content,
                embed=discord.Embed.from_dict(new_embed_dict),
            )
            await bot.db.starred_messages.create_starred_message(
                int(starred_message_data[-1]),
                starboard_message.id,
                extracted_star_amount,
                int(message.embeds[0].author.icon_url.split("/")[4]),
                int(starred_message_data[-2]),
            )
            continue

        reactions = next((reaction for reaction in starred_message.reactions if str(reaction.emoji) == "⭐"), None)
        if reactions is None:
            continue
        star_amount_list = [
            user async for user in reactions.users() if not user.bot and user.id != starred_message.author.id
        ]
        star_amount = len(star_amount_list)
        await cog.update_starboard(starred_message, star_amount)

        async with bot.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                for star_amount_user in star_amount_list:
                    await cur.execute(
                        """
                        INSERT INTO given_stars (user_id, given_star_amount)
                        VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE given_star_amount = given_star_amount + 1
                        """,
                        (star_amount_user.id, star_amount),
                    )
            await conn.commit()
        await message.delete()

    announce_message = await interaction.followup.send("移行処理が完了しました。")
    await sleep(3)
    await announce_message.delete()


@starboard_group.command(name="random", description="ランダムなスターボードを送信")
async def random_starboard(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    random_starred_message_data = await bot.db.starred_messages.get_random_starred_message()
    if random_starred_message_data is None:
        await interaction.response.send_message("ランダムなスターボードを取得できませんでした。", ephemeral=True)
        return
    starboard_channel = interaction.guild.get_channel(bot.config["starboard_channel_id"])
    if starboard_channel is None:
        await interaction.response.send_message("スターボードチャンネルが見つかりません。", ephemeral=True)
        return
    try:
        random_starboard_message = await starboard_channel.fetch_message(
            random_starred_message_data.starboard_message_id
        )
    except discord.NotFound:
        await interaction.response.send_message("ランダムなスターボードを取得できませんでした。", ephemeral=True)
        return
    await interaction.response.send_message(
        content=random_starboard_message.content, embeds=random_starboard_message.embeds
    )


@starboard_group.command(name="ranking", description="スターボードのランキングを表示")
async def starboard_ranking(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    starred_message_ranking = await bot.db.starred_messages.get_starred_message_ranking(5)
    star_amount_ranking = await bot.db.starred_messages.get_star_amount_ranking(5)
    given_star_ranking = await bot.db.given_stars.get_given_star_ranking(5)
    if len(starred_message_ranking) < 1 or len(star_amount_ranking) < 1 or len(given_star_ranking) < 1:
        await interaction.response.send_message("ランキングを作成するための情報が不足しています。")
        return

    cog = next((c for c in bot.cogs.values() if isinstance(c, Starboard)), None)
    raw_4_data_list = [
        (
            f"{cog.int_to_emoji(i)} : "
            f"[{starred_message.starred_message_id}]("
            f"https://discord.com/channels/{interaction.guild.id}/"
            f"{starred_message.starred_message_channel_id}/{starred_message.starred_message_id}"
            f") (⭐️ {starred_message.star_amount})"
        )
        for i, starred_message in enumerate(starred_message_ranking)
    ]
    raw_5_data_list = [
        f"{cog.int_to_emoji(i)} : <@{star_amount.user_id}>(⭐️ {star_amount.star_amount})"
        for i, star_amount in enumerate(star_amount_ranking)
    ]
    raw_6_data_list = [
        f"{cog.int_to_emoji(i)} : <@{given_star.user_id}> (⭐️ {given_star.given_star_amount})"
        for i, given_star in enumerate(given_star_ranking)
    ]
    base_embed = discord.Embed(color=discord.Color.random(), title="スターボードランキング")
    embeds = [
        base_embed.copy().add_field(name="星が最も多いメッセージ", value="\n".join(raw_4_data_list)),
        base_embed.copy().add_field(name="星をたくさん受け取ったユーザー", value="\n".join(raw_5_data_list)),
        base_embed.copy().add_field(name="星をたくさんあげたユーザー", value="\n".join(raw_6_data_list)),
    ]
    await Paginator(pages=embeds, show_disabled=False).respond(interaction)


async def setup(bot: AsteroidBot) -> None:
    register_setup_command(bot, migrate_starboard)
    register_group(bot, starboard_group)
    await bot.add_cog(Starboard(bot))
