from __future__ import annotations

from logging import getLogger

import discord
from discord.ext.commands import Bot

from app.database.manager import DatabaseManager
from app.database.session import create_engine, create_session_factory

from .config import AsteroidConfig
from .extensions import iter_enabled_extensions

logger = getLogger(__name__)


class AsteroidBot(Bot):
    def __init__(self, config: AsteroidConfig):
        self.config = config
        self.engine = create_engine(config)
        self.session_factory = create_session_factory(self.engine)
        self.db = DatabaseManager(config, self.engine, self.session_factory)
        self.repositories = self.db
        self.services: dict[str, object] = {}
        self.message_cache: dict[int, discord.Message] = {}

        super().__init__(
            command_prefix=(),
            help_command=None,
            intents=discord.Intents.all(),
            activity=discord.Activity(type=discord.ActivityType.watching, name=config.discord.activity_name),
            status=getattr(discord.Status, config.discord.status, discord.Status.dnd),
        )

    async def setup_hook(self) -> None:
        logger.info("セットアップを開始します。")
        await self._initialize_database()
        await self._load_extensions()
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

    async def _sync_slash_commands(self) -> None:
        if not self.config.discord.sync_commands_on_startup:
            logger.info("スラッシュコマンド同期をスキップします: sync_commands_on_startup=False")
            return

        if self.config.discord.register_globally or not self.config.discord.guild_ids:
            await self.tree.sync()
            logger.info("スラッシュコマンドをグローバル同期しました。")
            return

        for guild_id in self.config.discord.guild_ids:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info(f"スラッシュコマンドをギルド同期しました: guild_id={guild_id}")

    def remember_message(self, message: discord.Message) -> None:
        self.message_cache[message.id] = message
        if len(self.message_cache) > 2048:
            oldest_id = next(iter(self.message_cache))
            self.message_cache.pop(oldest_id, None)

    def get_message(self, message_id: int) -> discord.Message | None:
        return self.message_cache.get(message_id)

    async def close(self) -> None:
        logger.info("BOT の終了処理を開始します。")
        for cog in self.cogs.values():
            cleanup = getattr(cog, "cleanup_on_shutdown", None)
            if cleanup is not None:
                await cleanup()
        await self.engine.dispose()
        await super().close()
        logger.info("BOT の終了処理が完了しました。")
