from __future__ import annotations

from logging import getLogger

import discord
from discord.ext import commands

from app.core.bot import AsteroidBot
from app.features.roles.service import JoinRolesService
from app.features.welcomer.service import send_return_welcome

logger = getLogger(__name__)


class JoinRolesCog(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot
        self.service = JoinRolesService(bot)

    @commands.Cog.listener("on_member_remove")
    async def save_roles(self, member: discord.Member) -> None:
        if not self.bot.is_operating_guild(member.guild):
            return
        await self.service.save_user_roles(member)
        logger.debug(f"脱退メンバーのロールを保存しました: guild_id={member.guild.id} user_id={member.id}")

    @commands.Cog.listener("on_member_join")
    async def restore_or_give_roles(self, member: discord.Member) -> None:
        if not self.bot.is_operating_guild(member.guild):
            return

        restore_roles_count = await self.service.restore_user_roles(member)
        if restore_roles_count == 0:
            added_roles_count = await self.service.give_join_roles(member)
            if added_roles_count > 0:
                logger.debug(
                    f"参加時にロールを自動付与しました: guild_id={member.guild.id} "
                    f"user_id={member.id} role_count={added_roles_count}"
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
