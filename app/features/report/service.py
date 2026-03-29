from __future__ import annotations

from datetime import datetime

import discord

from app.common.constants import AsteroidColor


def build_report_embed(
    reporter: discord.User | discord.Member,
    content: str,
    image: discord.Attachment | None = None,
) -> discord.Embed:
    embed = discord.Embed(description=content, timestamp=datetime.now(), color=AsteroidColor.WARNING)
    embed.set_author(name=reporter.display_name, icon_url=reporter.display_avatar.url)
    embed.set_footer(text="未対応")
    if image is not None:
        embed.set_image(url=image.url)
    return embed


def build_resolved_report_embed(
    embed: discord.Embed,
    moderator: discord.User | discord.Member,
) -> discord.Embed:
    embed_dict = embed.to_dict()
    embed_dict["color"] = AsteroidColor.SUCCESS
    embed_dict["footer"] = {
        "text": f"{moderator.display_name} によって対応済み",
        "icon_url": moderator.display_avatar.url,
    }
    return discord.Embed.from_dict(embed_dict)
