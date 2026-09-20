from __future__ import annotations

from collections.abc import Awaitable, Callable
from logging import getLogger

import discord

from app.common.command_groups import get_bot
from app.common.discord_types import as_member
from app.common.guild_scope import GuildScopedView

from . import messages
from .service import ROLE_SELECT_LIMIT, role_is_manageable

logger = getLogger(__name__)
PanelRefreshCallback = Callable[[], Awaitable[None]]


def response_embed(title: str, description: str, *, color: int = 0xB2B1B5) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


def role_manage_error(guild: discord.Guild | None, role: discord.Role) -> str | None:
    if guild is None:
        return messages.ROLE_MANAGE_GUILD_REQUIRED
    if role == guild.default_role:
        return messages.ROLE_MANAGE_EVERYONE_REJECTED
    if role.managed:
        return messages.ROLE_MANAGE_MANAGED_REJECTED
    if not role_is_manageable(guild, role):
        return messages.ROLE_MANAGE_UNMANAGEABLE
    return None


def role_default_values(role_ids: list[int]) -> list[discord.SelectDefaultValue]:
    return [
        discord.SelectDefaultValue(id=role_id, type=discord.SelectDefaultValueType.role)
        for role_id in role_ids[:ROLE_SELECT_LIMIT]
    ]


class RolePanelAdminRoleSelect(discord.ui.RoleSelect["RolePanelAdminRoleEditView"]):
    def __init__(
        self,
        category_id: int,
        role_ids: list[int],
        actor_id: int,
        on_update: PanelRefreshCallback,
    ):
        super().__init__(
            custom_id=f"rolepanel_admin_roles:{category_id}:{actor_id}",
            placeholder=messages.ADMIN_ROLE_SELECT_PLACEHOLDER,
            min_values=0,
            max_values=ROLE_SELECT_LIMIT,
            default_values=role_default_values(role_ids),
        )
        self.category_id = category_id
        self.actor_id = actor_id
        self.on_update = on_update

    async def callback(self, interaction: discord.Interaction) -> None:
        actor = as_member(interaction.user)
        if interaction.user.id != self.actor_id and (actor is None or not actor.guild_permissions.administrator):
            logger.debug(
                "ロールパネル編集UIの操作を拒否しました: "
                f"guild_id={interaction.guild_id} actor_id={interaction.user.id} owner_id={self.actor_id} "
                f"category_id={self.category_id}"
            )
            await interaction.response.send_message(
                embed=response_embed(
                    messages.ROLE_EDIT_PERMISSION_REQUIRED.title, messages.ROLE_EDIT_PERMISSION_REQUIRED.description
                ),
                ephemeral=True,
            )
            return
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=response_embed(
                    messages.GUILD_EXECUTION_REQUIRED.title, messages.GUILD_EXECUTION_REQUIRED.description
                ),
                ephemeral=True,
            )
            return

        rejected_roles: list[discord.Role] = []
        role_ids: list[int] = []
        for role in self.values:
            if role_manage_error(interaction.guild, role) is not None:
                rejected_roles.append(role)
            else:
                role_ids.append(role.id)

        updated = await get_bot(interaction).db.role_panel.set_roles(self.category_id, role_ids)
        if updated is None:
            await interaction.response.send_message(
                embed=response_embed(messages.CATEGORY_NOT_FOUND.title, messages.CATEGORY_NOT_FOUND.description),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.on_update()
        rejected_role_ids = [role.id for role in rejected_roles]
        logger.info(
            "ロールパネルカテゴリのロールを同期しました: command=/rolepanel edit_role "
            f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
            f"category_id={self.category_id} role_ids={role_ids} rejected_role_ids={rejected_role_ids}"
        )
        message = messages.admin_role_update(
            role_count=len(role_ids),
            rejected_role_mentions=[role.mention for role in rejected_roles],
        )
        await interaction.followup.send(
            embed=response_embed(messages.ROLE_UPDATED_TITLE, message),
            ephemeral=True,
        )


class RolePanelAdminRoleEditView(GuildScopedView):
    def __init__(self, item: discord.ui.Item):
        super().__init__(timeout=300)
        self.add_item(item)
