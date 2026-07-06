from __future__ import annotations

from app.common.persistent_panels import PersistentPanelContent
from app.core.bot import AsteroidBot

from .views import AuthButton

AUTH_PANEL_ID = "auth"
AUTH_OFFLINE_DESCRIPTION = (
    "ご迷惑をおかけいたしますが、認証システムは現在利用できません。時間を空けてもう一度ご確認ください。"
)


class AuthPanel:
    def __init__(self, bot: AsteroidBot) -> None:
        self.bot = bot
        self.bot.panels.register(
            AUTH_PANEL_ID,
            self.bot.config.auth.panel_channel_id,
            self.render,
            offline_description=AUTH_OFFLINE_DESCRIPTION,
        )

    async def initialize(self) -> bool:
        return await self.bot.panels.initialize(AUTH_PANEL_ID)

    def unregister(self) -> None:
        self.bot.panels.unregister(AUTH_PANEL_ID)

    async def render(self) -> PersistentPanelContent:
        return PersistentPanelContent(
            embeds=(),
            view=AuthButton(self.bot, timeout=None),
        )
