from __future__ import annotations

import discord

from app.common.constants import AsteroidColor

from . import messages
from .service import MigrationPlan


def preview_embed(plan: MigrationPlan) -> discord.Embed:
    embed = discord.Embed(
        title=messages.PREVIEW_TITLE,
        description=messages.preview_accounts(plan.source.user_id, plan.target.user_id),
        color=AsteroidColor.INFO,
    )
    for name, value, inline in messages.preview_fields(plan.source, plan.target, plan.options, plan.discord):
        embed.add_field(name=name, value=value, inline=inline)
    embed.set_footer(text=messages.PREVIEW_FOOTER)
    return embed
