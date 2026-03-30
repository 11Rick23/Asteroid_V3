from __future__ import annotations

import discord

from app.core.config import get_config


async def send_first_welcome(member: discord.Member) -> None:
    config = get_config()
    welcome_channel_id = config.auth.welcome_channel_id
    if not welcome_channel_id:
        return

    channel = member.guild.get_channel(welcome_channel_id)
    if channel is None:
        return

    ping_role_id = config.auth.welcome_ping_role_id
    prefix = f"<@&{ping_role_id}>\n" if ping_role_id else ""
    await channel.send(f"{prefix}{member.mention}さん、ナメック星へようこそ！")


async def send_return_welcome(member: discord.Member) -> None:
    config = get_config()
    welcome_channel_id = config.auth.welcome_channel_id
    if not welcome_channel_id:
        return

    channel = member.guild.get_channel(welcome_channel_id)
    if channel is None:
        return

    ping_role_id = config.auth.welcome_ping_role_id
    prefix = f"<@&{ping_role_id}>\n" if ping_role_id else ""
    await channel.send(f"{prefix}{member.mention}さん、お帰りなさい！")
