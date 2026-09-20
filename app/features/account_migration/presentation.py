from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from app.common.constants import AsteroidColor
from app.common.guild_scope import GuildScopedLayoutView

from . import messages

if TYPE_CHECKING:
    from .service import MigrationPlan


class MigrationCheckView(GuildScopedLayoutView):
    def __init__(self, source_id: int, target_id: int, actor_id: int, status: str = messages.CHECKING) -> None:
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(f"## {messages.PREVIEW_TITLE}\n**{status}**"),
                discord.ui.Separator(),
                discord.ui.TextDisplay(messages.status_accounts(source_id, target_id, actor_id)),
                accent_color=AsteroidColor.INFO,
            )
        )


class MigrationPreviewLayout(GuildScopedLayoutView):
    def __init__(self, plan: MigrationPlan, actor_id: int) -> None:
        super().__init__(timeout=300)
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(f"## {messages.CHECK_READY}"),
                discord.ui.TextDisplay(messages.status_accounts(plan.source.user_id, plan.target.user_id, actor_id)),
                discord.ui.Separator(),
                discord.ui.TextDisplay(
                    messages.status_summary(plan.source, plan.target, plan.options, plan.discord, completed=False)
                ),
                discord.ui.Separator(),
                discord.ui.TextDisplay(f"### ⚠️ 確認事項\n{messages.PREVIEW_NOTE}\n\n-# {messages.PREVIEW_FOOTER}"),
                accent_color=AsteroidColor.INFO,
            )
        )
        self.add_item(discord.ui.File("attachment://account-migration.txt"))


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
