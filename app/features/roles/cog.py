from __future__ import annotations

from logging import getLogger

import discord
from discord.ext import commands

from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot
from app.features.welcomer.service import send_return_welcome

logger = getLogger(__name__)


class JoinRolesCog(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot

    @commands.Cog.listener("on_member_remove")
    async def save_roles(self, member: discord.Member) -> None:
        if member.guild.id not in self.bot.config.discord.guild_ids:
            return
        await self.bot.db.user_roles.save_user_roles(member)
        logger.debug(f"脱退メンバーのロールを保存しました: guild_id={member.guild.id} user_id={member.id}")

    @commands.Cog.listener("on_member_join")
    async def restore_or_give_roles(self, member: discord.Member) -> None:
        if member.guild.id not in self.bot.config.discord.guild_ids:
            return

        restore_roles_count = await self.bot.db.user_roles.restore_user_roles(member)
        if restore_roles_count == 0:
            add_roles: list[discord.Role] = []
            role_ids = (
                self.bot.config.roles.bot_join_role_id_list if member.bot else self.bot.config.roles.join_role_id_list
            )
            for role_id in role_ids:
                role = member.guild.get_role(role_id)
                if role is not None and role < member.guild.me.top_role:
                    add_roles.append(role)
                elif role is None:
                    logger.warning(
                        f"自動付与ロールが見つかりませんでした: guild_id={member.guild.id} role_id={role_id}"
                    )
            if add_roles:
                await member.add_roles(
                    *add_roles,
                    reason=f"[{generate_timestamp()}] 自動ロール付与機能により付与されました。",
                    atomic=False,
                )
                logger.debug(
                    f"参加時にロールを自動付与しました: guild_id={member.guild.id} "
                    f"user_id={member.id} role_count={len(add_roles)}"
                )
            else:
                logger.debug(
                    f"参加時に付与するロールがありませんでした: guild_id={member.guild.id} user_id={member.id}"
                )
        else:
            await send_return_welcome(member)
            logger.debug(
                f"再参加ユーザーのロールを復元しました: guild_id={member.guild.id} "
                f"user_id={member.id} restored_count={restore_roles_count}"
            )


async def setup(bot: AsteroidBot) -> None:
    await bot.add_cog(JoinRolesCog(bot))
