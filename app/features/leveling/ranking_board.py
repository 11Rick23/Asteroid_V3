from __future__ import annotations

import asyncio

from app.common.constants import AsteroidEmoji
from app.common.persistent_panels import PersistentPanelContent
from app.core.bot import AsteroidBot
from app.features.leveling.build_send_message import (
    LevelingLayoutView,
    build_hotness_ranking_container,
    build_power_ranking_pages,
    build_shard_ranking_pages,
)

from .messages import ranking as ranking_messages

RANKING_BOARD_PANEL_ID = "ranking_board"
RANKING_BOARD_LIMIT = 3


class RankingBoardPanel:
    def __init__(self, bot: AsteroidBot) -> None:
        self.bot = bot
        self.bot.panels.register(
            RANKING_BOARD_PANEL_ID,
            self.bot.config.leveling.ranking_board_channel_id,
            self.render,
            offline_description=ranking_messages.RANKING_OFFLINE_DESCRIPTION,
        )

    async def initialize(self) -> bool:
        return await self.bot.panels.initialize(RANKING_BOARD_PANEL_ID)

    async def refresh(self) -> bool:
        return await self.bot.panels.refresh(RANKING_BOARD_PANEL_ID)

    def unregister(self) -> None:
        self.bot.panels.unregister(RANKING_BOARD_PANEL_ID)

    async def render(self) -> PersistentPanelContent:
        monthly_powers, star_grades, hotness = await asyncio.gather(
            self.bot.db.monthly_powers.get_monthly_power_ranking(limit=RANKING_BOARD_LIMIT),
            self.bot.db.star_grades.get_star_grade_ranking(limit=RANKING_BOARD_LIMIT),
            self.bot.db.leveling_hotness.get_top_hotness(limit=RANKING_BOARD_LIMIT),
        )

        power_pages = build_power_ranking_pages(
            self.bot,
            monthly_powers,
            title=ranking_messages.POWER_RANKING_TITLE,
            description=ranking_messages.power_ranking_description(
                heading=ranking_messages.monthly_power_ranking_heading(limit=RANKING_BOARD_LIMIT),
                trailing=AsteroidEmoji.TRANSPARENT,
            ),
        )
        shard_pages = build_shard_ranking_pages(
            self.bot,
            star_grades,
            title=ranking_messages.SHARD_RANKING_TITLE,
            description=ranking_messages.shard_ranking_description(
                heading=ranking_messages.cumulative_shard_ranking_heading(limit=RANKING_BOARD_LIMIT),
                trailing=AsteroidEmoji.TRANSPARENT,
            ),
        )
        hotness_container = build_hotness_ranking_container(
            self.bot,
            hotness,
            title=ranking_messages.HOTNESS_RANKING_TITLE,
            description=ranking_messages.hotness_ranking_description(limit=RANKING_BOARD_LIMIT),
        )

        return PersistentPanelContent(
            embeds=(),
            view=LevelingLayoutView(
                shard_pages[0],
                power_pages[0],
                hotness_container,
                timeout=None,
            ),
        )
