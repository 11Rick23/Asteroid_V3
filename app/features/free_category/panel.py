from __future__ import annotations

from app.common.persistent_panels import PersistentPanelContent
from app.core.bot import AsteroidBot

from .service import get_free_category_service
from .views import CreateChannelButtonView

FREE_CATEGORY_PANEL_ID = "free_category"
FREE_CATEGORY_OFFLINE_DESCRIPTION = (
    "ご迷惑をおかけいたしますが、フリーチャンネル作成機能は現在利用できません。時間を空けてもう一度ご確認ください。"
)


class FreeCategoryPanel:
    def __init__(self, bot: AsteroidBot) -> None:
        self.bot = bot
        self.service = get_free_category_service(bot)
        self.bot.panels.register(
            FREE_CATEGORY_PANEL_ID,
            self.bot.config.free_category.text_create_channel_id,
            self.render,
            offline_description=FREE_CATEGORY_OFFLINE_DESCRIPTION,
        )

    async def initialize(self) -> bool:
        return await self.bot.panels.initialize(FREE_CATEGORY_PANEL_ID)

    def unregister(self) -> None:
        self.bot.panels.unregister(FREE_CATEGORY_PANEL_ID)

    async def render(self) -> PersistentPanelContent:
        return PersistentPanelContent(
            embeds=(),
            view=CreateChannelButtonView(self.service),
        )
