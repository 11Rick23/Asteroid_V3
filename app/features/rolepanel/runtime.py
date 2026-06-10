from __future__ import annotations

from logging import getLogger

import discord
from discord.ext import commands, tasks

from app.common.discord_types import as_messageable
from app.core.bot import AsteroidBot

from .service import get_rolepanel_service
from .views import RolePanelView

logger = getLogger(__name__)


class RolePanelCog(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot
        self.service = get_rolepanel_service(bot)
        self.role_panel_message: discord.Message | None = None
        self.initialize_role_panel.start()

    async def cog_unload(self) -> None:
        self.initialize_role_panel.cancel()

    async def cleanup_on_shutdown(self) -> None:
        await self._cleanup_role_panel_message()

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
            await self.send_or_update_role_panel()

    @initialize_role_panel.before_loop
    async def before_initialize_role_panel(self) -> None:
        await self.bot.wait_until_ready()

    @initialize_role_panel.after_loop
    async def cleanup_role_panel_after_loop(self) -> None:
        if self.initialize_role_panel.is_being_cancelled():
            await self._cleanup_role_panel_message()

    async def send_or_update_role_panel(self) -> bool:
        channel_id = self.bot.config.rolepanel.panel_channel_id
        channel = as_messageable(self.bot.get_channel(channel_id))
        if channel is None or not self.bot.is_operating_channel(channel):
            logger.warning(f"ロールパネル送信先チャンネルが見つかりませんでした: channel_id={channel_id}")
            return False

        categories = await self.service.get_categories()
        guild = channel.guild if isinstance(channel, discord.abc.GuildChannel) else None
        embed = self.service.build_panel_embed(categories, guild)
        view = RolePanelView(self.service, categories)
        if self.role_panel_message is None:
            try:
                self.role_panel_message = await channel.send(embed=embed, view=view)
            except discord.HTTPException:
                logger.exception(f"ロールパネルの初期化に失敗しました: channel_id={channel_id}")
                return False
            logger.info(
                f"ロールパネルを初期化しました: channel_id={channel_id} message_id={self.role_panel_message.id}"
            )
            return True

        try:
            await self.role_panel_message.edit(embed=embed, view=view)
        except discord.NotFound:
            logger.warning(
                f"ロールパネルメッセージが見つからなかったため再作成します: message_id={self.role_panel_message.id}"
            )
            try:
                self.role_panel_message = await channel.send(embed=embed, view=view)
            except discord.HTTPException:
                logger.exception(f"ロールパネルの再作成に失敗しました: channel_id={channel_id}")
                return False
            logger.info(
                f"ロールパネルを再作成しました: channel_id={channel_id} message_id={self.role_panel_message.id}"
            )
        except discord.HTTPException as error:
            logger.warning(
                "ロールパネルの更新に失敗しました。次回の編集または手動更新で再試行します: "
                f"message_id={self.role_panel_message.id} status={error.status} code={error.code}"
            )
            return False
        logger.debug(f"ロールパネルを更新しました: message_id={self.role_panel_message.id}")
        return True

    async def _cleanup_role_panel_message(self) -> None:
        if self.role_panel_message is None:
            return
        try:
            await self.role_panel_message.delete()
            logger.info(f"ロールパネルメッセージを削除しました: message_id={self.role_panel_message.id}")
        except discord.HTTPException:
            pass
        finally:
            self.role_panel_message = None


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
