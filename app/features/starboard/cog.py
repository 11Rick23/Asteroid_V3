from __future__ import annotations

import asyncio
from logging import getLogger

import discord
from discord import app_commands
from discord.ext import commands

from app.common.command_groups import get_bot, register_group, register_setup_command
from app.common.constants import AsteroidColor
from app.common.pages import Paginator
from app.core.bot import AsteroidBot

logger = getLogger(__name__)

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
        channel = guild.get_channel(event.channel_id)
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

            starboard_channel = self.bot.get_channel(self.bot.config.starboard.starboard_channel_id)
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
        starboard_channel = self.bot.get_channel(self.bot.config.starboard.starboard_channel_id)
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
        return f"{self.get_star_emoji(star_amount)} **{star_amount}** {starred_message.channel.mention}", embed

    def get_star_emoji(self, star_amount: int) -> str:
        return "🌟" if star_amount < 10 else "💫"

    def int_to_emoji(self, num: int) -> str:
        return ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"][num]


async def _find_existing_bot_message(
    channel: discord.abc.MessageableChannel, bot_user_id: int
) -> discord.Message | None:
    async for message in channel.history(limit=None):
        if message.author.id == bot_user_id:
            return message
    return None


def _build_starboard_setup_summary(total_count: int, recreated_count: int, deleted_count: int) -> str:
    return (
        "スターボード再作成が完了しました。\n"
        f"対象件数: {total_count}\n"
        f"再作成件数: {recreated_count}\n"
        f"欠損削除件数: {deleted_count}"
    )


def _build_starboard_setup_error(
    message: str,
    total_count: int,
    recreated_count: int,
    deleted_count: int,
    processed_count: int,
) -> str:
    return (
        f"{message}\n"
        f"対象件数: {total_count}\n"
        f"処理済み件数: {processed_count}\n"
        f"再作成件数: {recreated_count}\n"
        f"欠損削除件数: {deleted_count}"
    )


@app_commands.command(name="starboard", description="旧スターボードを再作成")
@app_commands.guild_only()
async def setup_starboard(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    await interaction.response.defer(ephemeral=True, thinking=True)
    logger.info(f"スターボード再作成を開始します: guild_id={interaction.guild.id if interaction.guild else None}")

    if interaction.guild is None or interaction.channel is None:
        await interaction.followup.send("サーバー内チャンネルで実行してください。", ephemeral=True)
        return

    source_starboard_channel = interaction.channel
    target_starboard_channel = interaction.guild.get_channel(bot.config.starboard.starboard_channel_id)
    if target_starboard_channel is None:
        logger.warning("スターボード再作成先チャンネルが未設定または未解決です。")
        await interaction.followup.send("スターボードチャンネル設定が不足しています。", ephemeral=True)
        return

    if source_starboard_channel.id == target_starboard_channel.id:
        await interaction.followup.send(
            "実行チャンネルとスターボードチャンネルが同一です。別の旧スターボードチャンネルで実行してください。",
            ephemeral=True,
        )
        return

    if bot.user is None:
        await interaction.followup.send("BOT ユーザー情報が取得できませんでした。", ephemeral=True)
        return

    existing_message = await _find_existing_bot_message(target_starboard_channel, bot.user.id)
    if existing_message is not None:
        logger.warning(
            "スターボード再作成を中止しました: reason=destination_already_has_bot_message "
            f"channel_id={target_starboard_channel.id} message_id={existing_message.id}"
        )
        await interaction.followup.send(
            "新しいスターボードチャンネルに既に BOT の投稿があります。再実行はできません。",
            ephemeral=True,
        )
        return

    starred_messages = await bot.db.starred_messages.get_all_starred_messages()
    total_count = len(starred_messages)
    recreated_count = 0
    deleted_count = 0

    for processed_count, starred_message_data in enumerate(starred_messages, start=1):
        try:
            old_starboard_message = await source_starboard_channel.fetch_message(
                starred_message_data.starboard_message_id
            )
        except discord.NotFound:
            await bot.db.starred_messages.delete_starred_message(starred_message_data.starred_message_id)
            deleted_count += 1
            logger.warning(
                "旧スターボード投稿が見つからなかったため DB から削除しました: "
                f"source_channel_id={source_starboard_channel.id} "
                f"old_starboard_message_id={starred_message_data.starboard_message_id} "
                f"starred_message_id={starred_message_data.starred_message_id}"
            )
            continue
        except discord.Forbidden:
            logger.warning(
                "旧スターボード投稿の取得権限がありません: "
                f"source_channel_id={source_starboard_channel.id} "
                f"old_starboard_message_id={starred_message_data.starboard_message_id}"
            )
            await interaction.followup.send(
                _build_starboard_setup_error(
                    "旧スターボードチャンネルのメッセージ取得権限がありません。処理を中断しました。",
                    total_count,
                    recreated_count,
                    deleted_count,
                    processed_count - 1,
                ),
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            logger.exception(
                "旧スターボード投稿の取得に失敗しました: "
                f"source_channel_id={source_starboard_channel.id} "
                f"old_starboard_message_id={starred_message_data.starboard_message_id}"
            )
            await interaction.followup.send(
                _build_starboard_setup_error(
                    "旧スターボードチャンネルのメッセージ取得に失敗しました。処理を中断しました。",
                    total_count,
                    recreated_count,
                    deleted_count,
                    processed_count - 1,
                ),
                ephemeral=True,
            )
            return

        try:
            new_starboard_message = await target_starboard_channel.send(
                content=old_starboard_message.content,
                embeds=old_starboard_message.embeds,
            )
        except discord.Forbidden:
            logger.warning(
                f"新スターボードチャンネルへの送信権限がありません: target_channel_id={target_starboard_channel.id}"
            )
            await interaction.followup.send(
                _build_starboard_setup_error(
                    "新しいスターボードチャンネルへの送信権限がありません。処理を中断しました。",
                    total_count,
                    recreated_count,
                    deleted_count,
                    processed_count - 1,
                ),
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            logger.exception(
                f"新スターボードチャンネルへの送信に失敗しました: target_channel_id={target_starboard_channel.id}"
            )
            await interaction.followup.send(
                _build_starboard_setup_error(
                    "新しいスターボードチャンネルへの送信に失敗しました。処理を中断しました。",
                    total_count,
                    recreated_count,
                    deleted_count,
                    processed_count - 1,
                ),
                ephemeral=True,
            )
            return

        await bot.db.starred_messages.set_starboard_message_id(
            starred_message_data.starred_message_id,
            new_starboard_message.id,
        )
        recreated_count += 1
        logger.debug(
            "スターボード投稿を再作成しました: "
            f"starred_message_id={starred_message_data.starred_message_id} "
            f"old_starboard_message_id={starred_message_data.starboard_message_id} "
            f"new_starboard_message_id={new_starboard_message.id}"
        )

    logger.info(
        "スターボード再作成が完了しました: "
        f"guild_id={interaction.guild.id} total_count={total_count} "
        f"recreated_count={recreated_count} deleted_count={deleted_count}"
    )
    await interaction.followup.send(
        _build_starboard_setup_summary(total_count, recreated_count, deleted_count),
        ephemeral=True,
    )


@starboard_group.command(name="random", description="ランダムなスターボードを送信")
async def random_starboard(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    random_starred_message_data = await bot.db.starred_messages.get_random_starred_message()
    if random_starred_message_data is None:
        logger.warning("ランダムなスターボードが取得できませんでした: reason=no_data")
        await interaction.response.send_message("ランダムなスターボードを取得できませんでした。", ephemeral=True)
        return
    starboard_channel = interaction.guild.get_channel(bot.config.starboard.starboard_channel_id)
    if starboard_channel is None:
        logger.warning("ランダムスターボード取得時にチャンネルが見つかりませんでした。")
        await interaction.response.send_message("スターボードチャンネルが見つかりません。", ephemeral=True)
        return
    try:
        random_starboard_message = await starboard_channel.fetch_message(
            random_starred_message_data.starboard_message_id
        )
    except discord.NotFound:
        logger.warning(
            f"ランダムスターボード取得時にメッセージが見つかりませんでした: "
            f"message_id={random_starred_message_data.starboard_message_id}"
        )
        await interaction.response.send_message("ランダムなスターボードを取得できませんでした。", ephemeral=True)
        return
    logger.debug(
        f"ランダムなスターボードを送信しました: guild_id={interaction.guild.id if interaction.guild else None} "
        f"message_id={random_starboard_message.id}"
    )
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
        logger.warning("スターボードランキング作成に必要な情報が不足しています。")
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
    logger.debug(
        f"スターボードランキングを表示しました: guild_id={interaction.guild.id if interaction.guild else None}"
    )
    await Paginator(pages=embeds, show_disabled=False).respond(interaction)


async def setup(bot: AsteroidBot) -> None:
    register_setup_command(bot, setup_starboard)
    register_group(bot, starboard_group)
    await bot.add_cog(Starboard(bot))
