from __future__ import annotations

from app.common.persistent_panels import PersistentPanelContent
from app.core.bot import AsteroidBot

from .service import get_rolepanel_service
from .views import RolePanelView

ROLE_PANEL_ID = "rolepanel"


class RolePanel:
    def __init__(self, bot: AsteroidBot) -> None:
        self.bot = bot
        self.service = get_rolepanel_service(bot)
        self.bot.panels.register(
            ROLE_PANEL_ID,
            self.bot.config.rolepanel.panel_channel_id,
            self.render,
        )

    async def initialize(self) -> bool:
        return await self.bot.panels.initialize(ROLE_PANEL_ID)

    async def refresh(self) -> bool:
        return await self.bot.panels.refresh(ROLE_PANEL_ID)

    def unregister(self) -> None:
        self.bot.panels.unregister(ROLE_PANEL_ID)

    async def render(self) -> PersistentPanelContent:
        categories = await self.service.get_categories()
        guild = self.bot.get_guild(self.bot.config.discord.guild_id)
        return PersistentPanelContent(
            embeds=(self.service.build_panel_embed(categories, guild),),
            view=RolePanelView(self.service, categories),
        )
