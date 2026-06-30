from __future__ import annotations

from discord.ext import commands, tasks

from app.common.error_reporting import report_background_task_error
from app.core.bot import AsteroidBot

from .panel import AuthPanel
from .views import AuthButton


class Authenticator(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot
        self.panel = AuthPanel(bot)
        self.initialize_panel.start()

    async def cog_load(self) -> None:
        self.bot.add_view(AuthButton(self.bot, timeout=None))

    async def cog_unload(self) -> None:
        self.initialize_panel.cancel()
        self.panel.unregister()

    @tasks.loop(count=1)
    async def initialize_panel(self) -> None:
        await self.panel.initialize()

    @initialize_panel.before_loop
    async def before_initialize_panel(self) -> None:
        await self.bot.wait_until_ready()

    @initialize_panel.error
    async def initialize_panel_error(self, error: BaseException) -> None:
        await report_background_task_error(self.bot, "auth.initialize_panel", error)


async def setup(bot: AsteroidBot) -> None:
    await bot.add_cog(Authenticator(bot))
