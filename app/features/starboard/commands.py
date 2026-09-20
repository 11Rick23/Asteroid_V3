from __future__ import annotations

from logging import getLogger

import discord
from discord import app_commands

from app.common.command_groups import get_bot
from app.common.discord_types import as_text_channel
from app.common.pages import Paginator
from app.common.permissions import admin_only

from . import messages

logger = getLogger(__name__)

starboard_group = app_commands.Group(name="starboard", description=messages.GROUP_DESCRIPTION)


async def _find_existing_bot_message(
    channel: discord.abc.MessageableChannel,
    bot_user_id: int,
) -> discord.Message | None:
    async for message in channel.history(limit=None):
        if message.author.id == bot_user_id:
            return message
    return None


@app_commands.command(name="starboard", description=messages.SETUP_DESCRIPTION)
@app_commands.guild_only()
@admin_only
async def setup_starboard(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    await interaction.response.defer(ephemeral=True, thinking=True)
    logger.info(
        "旧スターボード再作成を開始しました: command=/setup starboard "
        f"guild_id={getattr(interaction.guild, 'id', None)} "
        f"channel_id={getattr(interaction.channel, 'id', None)} "
        f"actor_id={getattr(getattr(interaction, 'user', None), 'id', None)}"
    )
    source_channel = as_text_channel(interaction.channel)
    if interaction.guild is None or source_channel is None:
        await interaction.followup.send(messages.SETUP_GUILD_CHANNEL_ONLY, ephemeral=True)
        return
    target_channel = as_text_channel(interaction.guild.get_channel(bot.config.starboard.starboard_channel_id))
    if target_channel is None:
        logger.warning("スターボード再作成先チャンネルが未設定または未解決です。")
        await interaction.followup.send(messages.SETUP_CHANNEL_MISSING, ephemeral=True)
        return
    if source_channel.id == target_channel.id:
        await interaction.followup.send(
            messages.SETUP_SAME_CHANNEL,
            ephemeral=True,
        )
        return
    if bot.user is None:
        await interaction.followup.send(messages.BOT_USER_MISSING, ephemeral=True)
        return
    existing_message = await _find_existing_bot_message(target_channel, bot.user.id)
    if existing_message is not None:
        logger.warning(
            "スターボード再作成を中止しました: reason=destination_already_has_bot_message "
            f"channel_id={target_channel.id} message_id={existing_message.id}"
        )
        await interaction.followup.send(
            messages.SETUP_ALREADY_RUN,
            ephemeral=True,
        )
        return

    starred_messages = await bot.db.starred_messages.get_all_starred_messages()
    total_count = len(starred_messages)
    recreated_count = 0
    deleted_count = 0
    for processed_count, data in enumerate(starred_messages, start=1):
        try:
            old_message = await source_channel.fetch_message(data.starboard_message_id)
        except discord.NotFound:
            deleted = await bot.db.starred_messages.delete_starred_message(data.starred_message_id)
            if deleted:
                deleted_count += 1
            logger.warning(
                "旧スターボード投稿が見つからなかったため DB から削除しました: "
                f"source_channel_id={source_channel.id} old_starboard_message_id={data.starboard_message_id} "
                f"starred_message_id={data.starred_message_id}"
            )
            continue
        except discord.Forbidden:
            logger.warning(
                "旧スターボード投稿の取得権限がありません: "
                f"source_channel_id={source_channel.id} old_starboard_message_id={data.starboard_message_id}"
            )
            await interaction.followup.send(
                messages.setup_error(
                    message=messages.SOURCE_READ_FORBIDDEN,
                    total_count=total_count,
                    recreated_count=recreated_count,
                    deleted_count=deleted_count,
                    processed_count=processed_count - 1,
                ),
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            logger.exception(
                "旧スターボード投稿の取得に失敗しました: "
                f"source_channel_id={source_channel.id} old_starboard_message_id={data.starboard_message_id}"
            )
            await interaction.followup.send(
                messages.setup_error(
                    message=messages.SOURCE_READ_FAILED,
                    total_count=total_count,
                    recreated_count=recreated_count,
                    deleted_count=deleted_count,
                    processed_count=processed_count - 1,
                ),
                ephemeral=True,
            )
            return
        try:
            new_message = await target_channel.send(content=old_message.content, embeds=old_message.embeds)
        except discord.Forbidden:
            logger.warning(f"新スターボードチャンネルへの送信権限がありません: target_channel_id={target_channel.id}")
            await interaction.followup.send(
                messages.setup_error(
                    message=messages.DESTINATION_SEND_FORBIDDEN,
                    total_count=total_count,
                    recreated_count=recreated_count,
                    deleted_count=deleted_count,
                    processed_count=processed_count - 1,
                ),
                ephemeral=True,
            )
            return
        except discord.HTTPException:
            logger.exception(f"新スターボードチャンネルへの送信に失敗しました: target_channel_id={target_channel.id}")
            await interaction.followup.send(
                messages.setup_error(
                    message=messages.DESTINATION_SEND_FAILED,
                    total_count=total_count,
                    recreated_count=recreated_count,
                    deleted_count=deleted_count,
                    processed_count=processed_count - 1,
                ),
                ephemeral=True,
            )
            return
        updated = await bot.db.starred_messages.set_starboard_message_id(data.starred_message_id, new_message.id)
        if not updated:
            logger.warning(
                "スターボード再作成対象が DB に存在しませんでした: "
                f"starred_message_id={data.starred_message_id} new_starboard_message_id={new_message.id}"
            )
            continue
        recreated_count += 1
        logger.debug(
            "スターボード投稿を再作成しました: "
            f"starred_message_id={data.starred_message_id} old_starboard_message_id={data.starboard_message_id} "
            f"new_starboard_message_id={new_message.id}"
        )
    logger.info(
        "旧スターボード再作成が完了しました: command=/setup starboard "
        f"guild_id={interaction.guild.id} channel_id={getattr(interaction.channel, 'id', None)} "
        f"actor_id={getattr(getattr(interaction, 'user', None), 'id', None)} "
        f"total_count={total_count} recreated_count={recreated_count} deleted_count={deleted_count}"
    )
    await interaction.followup.send(
        messages.setup_summary(
            total_count=total_count,
            recreated_count=recreated_count,
            deleted_count=deleted_count,
        ),
        ephemeral=True,
    )


@starboard_group.command(name="random", description=messages.RANDOM_DESCRIPTION)
async def random_starboard(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    data = await bot.db.starred_messages.get_random_starred_message()
    if data is None:
        logger.warning("ランダムなスターボードが取得できませんでした: reason=no_data")
        await interaction.response.send_message(messages.RANDOM_NOT_FOUND, ephemeral=True)
        return
    if interaction.guild is None:
        await interaction.response.send_message(messages.GUILD_ONLY, ephemeral=True)
        return
    channel = as_text_channel(interaction.guild.get_channel(bot.config.starboard.starboard_channel_id))
    if channel is None:
        logger.warning("ランダムスターボード取得時にチャンネルが見つかりませんでした。")
        await interaction.response.send_message(messages.CHANNEL_NOT_FOUND, ephemeral=True)
        return
    try:
        message = await channel.fetch_message(data.starboard_message_id)
    except discord.NotFound:
        logger.warning(
            f"ランダムスターボード取得時にメッセージが見つかりませんでした: message_id={data.starboard_message_id}"
        )
        await interaction.response.send_message(messages.RANDOM_NOT_FOUND, ephemeral=True)
        return
    logger.debug(
        "ランダムスターボードを送信しました: command=/starboard random "
        f"guild_id={interaction.guild.id} channel_id={interaction.channel_id} "
        f"user_id={interaction.user.id} message_id={message.id}"
    )
    await interaction.response.send_message(content=message.content, embeds=message.embeds)


def _ranking_emoji(index: int) -> str:
    return ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"][index]


@starboard_group.command(name="ranking", description=messages.RANKING_DESCRIPTION)
async def starboard_ranking(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    message_ranking = await bot.db.starred_messages.get_starred_message_ranking(5)
    star_ranking = await bot.db.starred_messages.get_star_amount_ranking(5)
    given_ranking = await bot.db.given_stars.get_given_star_ranking(5)
    if not message_ranking or not star_ranking or not given_ranking or interaction.guild is None:
        logger.warning("スターボードランキング作成に必要な情報が不足しています。")
        await interaction.response.send_message(messages.RANKING_DATA_MISSING)
        return
    message_lines = [
        (
            messages.message_ranking_line(
                emoji=_ranking_emoji(index),
                guild_id=interaction.guild.id,
                channel_id=data.starred_message_channel_id,
                message_id=data.starred_message_id,
                stars=data.star_amount,
            )
        )
        for index, data in enumerate(message_ranking)
    ]
    star_lines = [
        messages.user_ranking_line(
            emoji=_ranking_emoji(index),
            user_id=data.user_id,
            stars=data.star_amount,
            compact=True,
        )
        for index, data in enumerate(star_ranking)
    ]
    given_lines = [
        messages.user_ranking_line(emoji=_ranking_emoji(index), user_id=data.user_id, stars=data.given_star_amount)
        for index, data in enumerate(given_ranking)
    ]
    base_embed = discord.Embed(color=discord.Color.random(), title=messages.RANKING_TITLE)
    embeds = [
        base_embed.copy().add_field(name=messages.MOST_STARRED_MESSAGE_FIELD, value="\n".join(message_lines)),
        base_embed.copy().add_field(name=messages.MOST_STARRED_USER_FIELD, value="\n".join(star_lines)),
        base_embed.copy().add_field(name=messages.MOST_GIVEN_USER_FIELD, value="\n".join(given_lines)),
    ]
    logger.debug(
        "スターボードランキングを表示しました: command=/starboard ranking "
        f"guild_id={interaction.guild.id} channel_id={interaction.channel_id} user_id={interaction.user.id}"
    )
    await Paginator(pages=embeds, show_disabled=False).respond(interaction)
