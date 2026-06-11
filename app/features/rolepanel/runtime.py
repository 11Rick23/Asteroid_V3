from __future__ import annotations

from logging import getLogger

import discord
from discord.ext import commands, tasks

from app.core.bot import AsteroidBot

from .panel import RolePanel
from .service import get_rolepanel_service

logger = getLogger(__name__)


class RolePanelCog(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot
        self.service = get_rolepanel_service(bot)
        self.role_panel = RolePanel(bot)
        self.initialize_role_panel.start()

    async def cog_unload(self) -> None:
        self.initialize_role_panel.cancel()
        self.role_panel.unregister()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if not self.bot.is_operating_guild(after.guild):
            return
        if before.premium_since is None or after.premium_since is not None:
            return
        try:
            await self.service.remove_boost_required_roles(after)
        except discord.HTTPException as error:
            logger.warning(
                "ブースト解除時のロール削除に失敗しました: "
                f"guild_id={after.guild.id} user_id={after.id} status={error.status} code={error.code}"
            )

    @tasks.loop(count=1)
    async def initialize_role_panel(self) -> None:
        if self.bot.db.is_initialized():
            await self.role_panel.initialize()

    @initialize_role_panel.before_loop
    async def before_initialize_role_panel(self) -> None:
        await self.bot.wait_until_ready()

    async def send_or_update_role_panel(self) -> bool:
        return await self.role_panel.refresh()


def get_rolepanel_cog(bot: AsteroidBot) -> RolePanelCog | None:
    cog = bot.get_cog("RolePanelCog")
    return cog if isinstance(cog, RolePanelCog) else None


async def refresh_panel_if_loaded(bot: AsteroidBot) -> None:
    cog = get_rolepanel_cog(bot)
    if cog is not None:
        try:
            await cog.send_or_update_role_panel()
        except Exception:
            logger.exception("ロールパネルの再描画中に予期しないエラーが発生しました。")
