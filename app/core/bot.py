from logging import getLogger

import discord
from discord import app_commands
from discord.ext.commands import Bot

from .config import AsteroidConfig

logger = getLogger(__name__)


class AsteroidBot(Bot):
    def __init__(self, config: AsteroidConfig):
        self.config = config
        # self.engine: AsyncEngine
        """データベースのエンジン。こちらは基本的に使用しない。"""
        # self.session: async_sessionmaker
        """
        データベースのセッションメーカー。こちらを使用する。

        使用例1:
        ```python
        async with self.bot.session() as session:
            # データベースの処理
            await session.commit()  # もちろんデータ取得のみならcommitは不要
        ```
        使用例2:
        ```python
        async with self.bot.session.begin() as session:
            # データベースの処理
            # commitは不要
        ```
        """
        # self.app_command_cache: dict[str, app_commands.AppCommand] = {}

        super().__init__(
            command_prefix=(),
            help_command=None,
            intents=discord.Intents.all(),
            activity=discord.Activity(type=discord.ActivityType.watching, name="ナメック星"),
            status=discord.Status.dnd,
        )

    # async def setup_hook(self):
    #     self.engine = await setup_database()
    #     self.session = async_sessionmaker(self.engine, expire_on_commit=False)

    #     for module in self.config.get("module_list"):
    #         logger.debug(f"モジュール {module} を読み込みます。")
    #         await self.load_extension(module)

    #     self.tree.allowed_contexts = discord.app_commands.AppCommandContext(
    #         guild=True, dm_channel=False, private_channel=False
    #     )
    #     self.tree.allowed_installs = discord.app_commands.AppInstallationType(guild=True, user=False)

    #     if self.config.get("sync_slash_commands_on_startup"):
    #         await self.sync_slash_commands()
    #     else:
    #         await self.cache_app_commands()

    # def get_app_command_by_name(
    #     self,
    #     name: str,
    # ) -> app_commands.AppCommand | None:
    #     """
    #     スラッシュコマンドをスラッシュコマンド名から取得できる。

    #     階層になっているコマンドは、`"group_name command_name"`のように指定することで取得できる。
    #     """
    #     return self.app_command_cache.get(name)

    # async def sync_slash_commands(self):
    #     if self.config.get("register_slash_commands_globally"):
    #         logger.info("グローバルにスラッシュコマンドを同期します。")
    #         await self.tree.sync()
    #         guild = None

    #     else:
    #         logger.info("ギルドごとにスラッシュコマンドを同期します。")

    #         guild_id = self.config.get("guild_id")

    #         logger.debug(f"ギルド {guild_id} にスラッシュコマンドを{len(self.tree._get_all_commands())}個同期します。")

    #         guild = discord.Object(id=guild_id)
    #         self.tree.copy_global_to(guild=guild)
    #         await self.tree.sync(guild=guild)

    #     logger.debug("スラッシュコマンドの同期が完了しました。")

    #     await self.cache_app_commands()

    # async def cache_app_commands(self):
    #     logger.debug("スラッシュコマンドのキャッシュを保存します。")

    #     def unpack_options(
    #         options: list[app_commands.AppCommand | app_commands.AppCommandGroup | app_commands.Argument],
    #     ):
    #         for option in options:
    #             if isinstance(option, app_commands.AppCommandGroup):
    #                 self.app_command_cache[option.qualified_name] = option
    #                 unpack_options(option.options)

    #     guild = (
    #         None
    #         if self.config.get("register_slash_commands_globally")
    #         else discord.Object(id=self.config.get("guild_id"))
    #     )
    #     commands: list[app_commands.AppCommand] = await self.tree.fetch_commands(guild=guild)

    #     for command in commands:
    #         self.app_command_cache[command.name] = command
    #         unpack_options(command.options)

    #     logger.debug("スラッシュコマンドのキャッシュを保存しました。")

    # async def close(self):
    #     await self.engine.dispose()
    #     return await super().close()
