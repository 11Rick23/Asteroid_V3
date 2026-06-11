from __future__ import annotations

import asyncio
from logging import getLogger

import discord
from discord.ext.commands import Bot

from app.common.constants import AsteroidColor
from app.common.guild_scope import OperatingGuildCommandTree
from app.common.offline import OfflineInfo
from app.common.persistent_panels import PersistentPanelManager
from app.database.manager import DatabaseManager
from app.database.session import create_engine, create_session_factory

from .config import AsteroidConfig
from .extensions import iter_enabled_extensions

logger = getLogger(__name__)


class AsteroidBot(Bot):
    def __init__(self, config: AsteroidConfig):
        if not config.discord.guild_id:
            raise RuntimeError("config.discord.guild_id を設定してください。")

        self.config = config
        self.engine = create_engine(config)
        self.session_factory = create_session_factory(self.engine)
        self.db = DatabaseManager(config, self.engine, self.session_factory)
        self.repositories = self.db
        self.services: dict[str, object] = {}
        self.panels = PersistentPanelManager(self)
        self.message_cache: dict[int, discord.Message] = {}
        self.shutdown_requested = False
        self.shutdown_task: asyncio.Task[None] | None = None
        self._close_lock = asyncio.Lock()
        self._shutdown_cleanup_complete = False

        super().__init__(
            command_prefix=(),
            help_command=None,
            tree_cls=OperatingGuildCommandTree,
            intents=discord.Intents.all(),
            activity=discord.Activity(type=discord.ActivityType.watching, name=config.discord.activity_name),
            status=getattr(discord.Status, config.discord.status, discord.Status.dnd),
        )

    def is_operating_guild_id(self, guild_id: int | None) -> bool:
        return guild_id is not None and guild_id == self.config.discord.guild_id

    def is_operating_guild(self, guild: discord.Guild | None) -> bool:
        return guild is not None and self.is_operating_guild_id(guild.id)

    def is_operating_channel(self, channel: object) -> bool:
        return self.is_operating_guild(getattr(channel, "guild", None))

    async def setup_hook(self) -> None:
        logger.info("セットアップを開始します。")
        await self._initialize_database()
        await self._load_extensions()
        self._register_system_commands()
        await self._sync_slash_commands()
        logger.info("セットアップが完了しました。")

    async def _initialize_database(self) -> None:
        logger.info("データベース初期化を開始します。")
        table_initializers = (
            self.db.user_roles.create_table,
            self.db.given_stars.create_table,
            self.db.starred_messages.create_table,
            self.db.xp_boosts.create_table,
            self.db.star_grades.create_table,
            self.db.voice_xp_limits.create_table,
            self.db.monthly_action_powers.create_table,
            self.db.monthly_powers.create_table,
            self.db.user_birthdays.create_table,
            self.db.role_panel.create_table,
        )
        for create_table in table_initializers:
            await create_table()
        self.db.initialized = True
        logger.info(f"データベース初期化が完了しました: table_count={len(table_initializers)}")

    async def _load_extensions(self) -> None:
        extensions = list(iter_enabled_extensions(self.config))
        for extension in extensions:
            logger.debug(f"Loading extension {extension}")
            await self.load_extension(extension)
        logger.info(f"拡張機能の読み込みが完了しました: count={len(extensions)}")

    def _register_system_commands(self) -> None:
        from .system_commands import register_system_commands

        register_system_commands(self)

    async def _sync_slash_commands(self) -> None:
        if not self.config.discord.sync_commands_on_startup:
            logger.info("スラッシュコマンド同期をスキップします: sync_commands_on_startup=False")
            return

        if self.config.discord.register_globally or not self.config.discord.guild_id:
            await self.tree.sync()
            logger.info("スラッシュコマンドをグローバル同期しました。")
            return

        guild = discord.Object(id=self.config.discord.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        logger.info(f"スラッシュコマンドをギルド同期しました: guild_id={self.config.discord.guild_id}")

    def remember_message(self, message: discord.Message) -> None:
        self.message_cache[message.id] = message
        if len(self.message_cache) > 2048:
            oldest_id = next(iter(self.message_cache))
            self.message_cache.pop(oldest_id, None)

    def get_message(self, message_id: int) -> discord.Message | None:
        return self.message_cache.get(message_id)

    def schedule_graceful_shutdown(self, info: OfflineInfo) -> bool:
        if self.shutdown_requested:
            return False

        self.shutdown_requested = True
        self.shutdown_task = asyncio.create_task(
            self.shutdown_gracefully(info),
            name="asteroid-graceful-shutdown",
        )
        return True

    async def set_offline_presence(self) -> None:
        try:
            await self.change_presence(status=discord.Status.offline, activity=None)
        except Exception:
            logger.warning("BOT ステータスをオフラインに変更できませんでした。停止処理は続行します。", exc_info=True)
            return
        logger.info("BOT ステータスをオフラインに変更しました。")

    async def send_shutdown_start_message(self, info: OfflineInfo) -> None:
        channel_id = self.config.log.main_log_channel_id
        if not channel_id:
            logger.debug("BOT 終了通知をスキップしました: main_log_channel_id=0")
            return

        channel = self.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.fetch_channel(channel_id)
            except discord.HTTPException:
                return

        if not isinstance(channel, discord.abc.Messageable):
            return
        if not self.is_operating_channel(channel):
            logger.warning(
                f"BOT終了通知先が稼働ギルド外です: guild_id={self.config.discord.guild_id} channel_id={channel_id}"
            )
            return

        embed = discord.Embed(
            title="BOT の停止処理を開始します",
            color=AsteroidColor.WARNING,
        )
        embed.add_field(name="理由", value=info.reason, inline=False)
        embed.add_field(name="予定期間", value=info.planned_period, inline=False)

        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            return

    async def shutdown_gracefully(self, info: OfflineInfo) -> None:
        logger.info(
            f"BOT の停止処理を開始します: reason={info.reason} planned_period={info.planned_period}"
        )
        try:
            await self.panels.set_all_offline(info)
            await self.send_shutdown_start_message(info)
            await self.set_offline_presence()
            await self.close()
        except Exception:
            self.shutdown_requested = False
            logger.exception(
                f"BOT の停止に失敗しました: reason={info.reason} planned_period={info.planned_period}"
            )

    async def close(self) -> None:
        async with self._close_lock:
            if self._shutdown_cleanup_complete:
                logger.debug("BOT の停止処理は既に完了しています。")
                return

            logger.info("BOT の停止処理を開始します。")
            for cog in self.cogs.values():
                cleanup = getattr(cog, "cleanup_on_shutdown", None)
                if cleanup is not None:
                    try:
                        await cleanup()
                    except Exception:
                        logger.exception(
                            f"Cog の停止処理に失敗しました。終了処理は続行します: cog={cog.qualified_name}"
                        )
            try:
                await self.engine.dispose()
            except Exception:
                logger.exception("データベース接続の終了に失敗しました。Discord 接続の終了処理は続行します。")
            await super().close()
            self._shutdown_cleanup_complete = True
            logger.info("BOT の停止処理が完了しました。")
