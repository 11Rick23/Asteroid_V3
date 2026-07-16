from __future__ import annotations

from logging import getLogger

import discord

from app.common.discord_types import as_messageable
from app.core.config import get_config

from . import messages

logger = getLogger(__name__)


async def send_first_welcome(member: discord.Member) -> None:
    config = get_config()
    welcome_channel_id = config.auth.welcome_channel_id
    if not welcome_channel_id:
        logger.warning(f"初回ウェルカム送信先が未設定です: guild_id={member.guild.id} user_id={member.id}")
        return

    channel = as_messageable(member.guild.get_channel(welcome_channel_id))
    if channel is None:
        logger.warning(
            f"初回ウェルカム送信先が見つかりませんでした: guild_id={member.guild.id} "
            f"channel_id={welcome_channel_id} user_id={member.id}"
        )
        return

    ping_role_id = config.auth.welcome_ping_role_id
    prefix = f"<@&{ping_role_id}>\n" if ping_role_id else ""
    await channel.send(messages.first_welcome(prefix=prefix, member_mention=member.mention))
    logger.debug(
        f"初回ウェルカムを送信しました: guild_id={member.guild.id} "
        f"channel_id={getattr(channel, 'id', None)} user_id={member.id}"
    )


async def send_return_welcome(member: discord.Member) -> None:
    config = get_config()
    welcome_channel_id = config.auth.welcome_channel_id
    if not welcome_channel_id:
        logger.warning(f"再参加ウェルカム送信先が未設定です: guild_id={member.guild.id} user_id={member.id}")
        return

    channel = as_messageable(member.guild.get_channel(welcome_channel_id))
    if channel is None:
        logger.warning(
            f"再参加ウェルカム送信先が見つかりませんでした: guild_id={member.guild.id} "
            f"channel_id={welcome_channel_id} user_id={member.id}"
        )
        return

    ping_role_id = config.auth.welcome_ping_role_id
    prefix = f"<@&{ping_role_id}>\n" if ping_role_id else ""
    await channel.send(messages.return_welcome(prefix=prefix, member_mention=member.mention))
    logger.debug(
        f"再参加ウェルカムを送信しました: guild_id={member.guild.id} "
        f"channel_id={getattr(channel, 'id', None)} user_id={member.id}"
    )
