from __future__ import annotations

from typing import cast

import discord


def as_messageable(channel: object) -> discord.abc.Messageable | None:
    return channel if isinstance(channel, discord.abc.Messageable) else None


def as_member(user: discord.User | discord.Member) -> discord.Member | None:
    return user if isinstance(user, discord.Member) else None


def as_text_channel(channel: object) -> discord.TextChannel | None:
    if isinstance(channel, discord.TextChannel):
        return channel
    if all(hasattr(channel, attr) for attr in ("fetch_message", "history", "send", "id")):
        return cast(discord.TextChannel, channel)
    return None
