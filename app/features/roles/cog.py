from __future__ import annotations

import discord
from discord.ext import commands

from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot


class JoinRolesCog(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot

    @commands.Cog.listener("on_member_remove")
    async def save_roles(self, member: discord.Member) -> None:
        if member.guild.id not in self.bot.config["guild_id_list"]:
            return
        await self.bot.db.user_roles.save_user_roles(member)

    @commands.Cog.listener("on_member_join")
    async def restore_or_give_roles(self, member: discord.Member) -> None:
        if member.guild.id not in self.bot.config["guild_id_list"]:
            return

        restore_roles_count = await self.bot.db.user_roles.restore_user_roles(member)
        if restore_roles_count == 0:
            add_roles: list[discord.Role] = []
            role_ids = self.bot.config["bot_join_role_id_list"] if member.bot else self.bot.config["join_role_id_list"]
            for role_id in role_ids:
                role = member.guild.get_role(role_id)
                if role is not None and role < member.guild.me.top_role:
                    add_roles.append(role)
            if add_roles:
                await member.add_roles(
                    *add_roles,
                    reason=f"[{generate_timestamp()}] 自動ロール付与機能により付与されました。",
                    atomic=False,
                )
        else:
            welcome_channel_id = self.bot.config.get("welcome_channel_id")
            channel = self.bot.get_channel(welcome_channel_id) if welcome_channel_id else None
            if channel is not None:
                await channel.send(f"<@&818789324165873664>\n{member.mention}さん、お帰りなさい！")


async def setup(bot: AsteroidBot) -> None:
    await bot.add_cog(JoinRolesCog(bot))
