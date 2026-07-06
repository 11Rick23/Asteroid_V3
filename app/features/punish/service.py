from __future__ import annotations

import datetime
from logging import getLogger

import discord

from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot

logger = getLogger(__name__)


def generate_reason(moderator: discord.Member) -> str:
    return f"[{generate_timestamp()}] {moderator.name} によって処罰が行われました。"


def log_punishment_action(
    action: str,
    interaction: discord.Interaction,
    target_id: int,
    *,
    probation: str | None = None,
    duration: str | None = None,
) -> None:
    logger.info(
        f"処罰を実行します: action={action} "
        f"guild_id={interaction.guild.id if interaction.guild is not None else None} "
        f"moderator_id={interaction.user.id} target_id={target_id} "
        f"probation={probation} duration={duration}"
    )


async def send_punish_message(
    punishment_board: discord.TextChannel,
    user: discord.User | discord.Member,
    reason: str,
    punishment: str,
    probation: str | None,
    duration: str | None = None,
) -> None:
    message = (
        f"```{user.name} {user.id}\n"
        f"日付: {datetime.datetime.now().strftime('%m/%d')}\n"
        f"違反内容: {reason}\n"
        f"処罰: {punishment}"
        + (f"\n期間: {duration}" if duration is not None else "")
        + (f"\n執行猶予: {probation}```" if probation is not None else "```")
    )
    await punishment_board.send(message)
    try:
        await user.send(message)
    except discord.Forbidden:
        logger.debug(f"処罰DMの送信に失敗しました: target_id={user.id}")


async def require_punishment_context(
    bot: AsteroidBot,
    interaction: discord.Interaction,
) -> tuple[discord.Guild, discord.Member, discord.TextChannel] | None:
    if interaction.guild is None or not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("サーバー内でのみ使用できます。", ephemeral=True)
        return None
    punishment_board = interaction.guild.get_channel(bot.config.punish.punishment_board_channel_id)
    if not isinstance(punishment_board, discord.TextChannel):
        logger.warning(
            "処罰板チャンネルが見つかりませんでした: "
            f"guild_id={interaction.guild.id} channel_id={bot.config.punish.punishment_board_channel_id}"
        )
        await interaction.response.send_message("処罰板チャンネルが見つかりません。", ephemeral=True)
        return None
    return interaction.guild, interaction.user, punishment_board


async def give_crime_record_role(
    bot: AsteroidBot,
    guild: discord.Guild,
    user: discord.User | discord.Member,
    moderator: discord.Member,
) -> bool:
    member = guild.get_member(user.id)
    if member is None:
        logger.warning(f"前科ロールの付与対象メンバーが見つかりませんでした: guild_id={guild.id} target_id={user.id}")
        return True

    crimes = sum(1 for role in member.roles if role.name.startswith("前科"))
    crime_roles = bot.config.punish.crime_record_role_id_list
    if crimes < len(crime_roles):
        role = guild.get_role(crime_roles[crimes])
        if role is not None:
            await member.add_roles(role, reason=generate_reason(moderator))
            logger.debug(f"前科ロールを付与しました: guild_id={guild.id} target_id={user.id} role_id={role.id}")
        else:
            logger.warning(
                f"前科ロールが見つかりませんでした: guild_id={guild.id} "
                f"target_id={user.id} role_id={crime_roles[crimes]}"
            )
    return False
