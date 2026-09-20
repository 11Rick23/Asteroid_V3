from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from app.common.constants import AsteroidColor
from app.common.guild_scope import GuildScopedLayoutView

from . import messages

if TYPE_CHECKING:
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


class MigrationStatusView(GuildScopedLayoutView):
    def __init__(self, plan: MigrationPlan, actor_id: int, status: str, *, include_restore: bool = False) -> None:
        super().__init__(timeout=None)
        if status == messages.PROCESSING:
            color = AsteroidColor.ORANGE
        elif status == messages.COMPLETED:
            color = AsteroidColor.GREEN
        elif status in (messages.CANCELLED, messages.STOPPED):
            color = AsteroidColor.INFO
        else:
            color = AsteroidColor.WARNING
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(f"## {messages.PREVIEW_TITLE}\n**{status}**"),
                discord.ui.TextDisplay(messages.status_accounts(plan.source.user_id, plan.target.user_id, actor_id)),
                discord.ui.Separator(),
                discord.ui.TextDisplay(
                    messages.status_summary(
                        plan.source, plan.target, plan.options, plan.discord, completed=status == messages.COMPLETED
                    )
                ),
                accent_color=color,
            )
        )
        if include_restore and plan.options.leveling:
            self.add_item(
                discord.ui.Container(
                    discord.ui.TextDisplay(f"### {messages.RESTORE_TITLE}\n{messages.RESTORE_NOTE}"),
                    discord.ui.Separator(),
                    discord.ui.TextDisplay(messages.restore_block(plan.source, source=True)),
                    discord.ui.Separator(),
                    discord.ui.TextDisplay(messages.restore_block(plan.target, source=False)),
                    accent_color=AsteroidColor.INFO,
                )
            )
        self.add_item(discord.ui.File("attachment://account-migration.txt"))
