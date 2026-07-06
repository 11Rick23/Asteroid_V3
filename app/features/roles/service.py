from __future__ import annotations

from logging import getLogger

import discord

from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot

logger = getLogger(__name__)


def get_save_role_ids(member: discord.Member, ignored_role_ids: list[int]) -> list[int]:
    return [
        role.id
        for role in member.roles
        if role != member.guild.default_role and role < member.guild.me.top_role and role.id not in ignored_role_ids
    ]


def get_restorable_roles(member: discord.Member, role_ids: list[int]) -> tuple[list[discord.Role], list[int]]:
    roles: list[discord.Role] = []
    missing_role_ids: list[int] = []
    for role_id in role_ids:
        role = member.guild.get_role(role_id)
        if role is None:
            missing_role_ids.append(role_id)
        elif role < member.guild.me.top_role:
            roles.append(role)
    return roles, missing_role_ids


class JoinRolesService:
    def __init__(self, bot: AsteroidBot):
        self.bot = bot

    async def save_user_roles(self, member: discord.Member) -> None:
        role_ids = get_save_role_ids(member, self.bot.config.roles.ignored_save_role_id_list)
        await self.bot.db.user_roles.save_user_roles(member.id, role_ids)

    async def restore_user_roles(self, member: discord.Member) -> int:
        roles_data = await self.bot.db.user_roles.get_user_roles(member.id)
        roles, missing_role_ids = get_restorable_roles(member, [role.role_id for role in roles_data])
        for role_id in missing_role_ids:
            await self.bot.db.user_roles.delete_user_role(member.id, role_id)

        if roles:
            await member.add_roles(
                *roles,
                reason=f"[{generate_timestamp()}] ロール復元機能により付与されました。",
                atomic=False,
            )
        return len(roles)

    async def give_join_roles(self, member: discord.Member) -> int:
        add_roles: list[discord.Role] = []
        role_ids = (
            self.bot.config.roles.bot_join_role_id_list if member.bot else self.bot.config.roles.join_role_id_list
        )
        for role_id in role_ids:
            role = member.guild.get_role(role_id)
            if role is not None and role < member.guild.me.top_role:
                add_roles.append(role)
            elif role is None:
                logger.warning(f"自動付与ロールが見つかりませんでした: guild_id={member.guild.id} role_id={role_id}")

        if not add_roles:
            return 0

        await member.add_roles(
            *add_roles,
            reason=f"[{generate_timestamp()}] 自動ロール付与機能により付与されました。",
            atomic=False,
        )
        return len(add_roles)
