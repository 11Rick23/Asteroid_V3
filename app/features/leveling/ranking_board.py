from __future__ import annotations

from app.common.constants import AsteroidEmoji
from app.common.persistent_panels import PersistentPanelContent
from app.core.bot import AsteroidBot
from app.features.leveling.build_send_message import (
    LevelingLayoutView,
    build_power_ranking_pages,
    build_shard_ranking_pages,
)

RANKING_BOARD_PANEL_ID = "ranking_board"
RANKING_BOARD_OFFLINE_DESCRIPTION = (
    "ご迷惑をおかけいたしますが、ランキングは現在確認できません。時間を空けてもう一度ご確認ください。"
)


class RankingBoardPanel:
    def __init__(self, bot: AsteroidBot) -> None:
        self.bot = bot
        self.bot.panels.register(
            RANKING_BOARD_PANEL_ID,
            self.bot.config.leveling.ranking_board_channel_id,
            self.render,
            offline_description=RANKING_BOARD_OFFLINE_DESCRIPTION,
        )

    async def initialize(self) -> bool:
        return await self.bot.panels.initialize(RANKING_BOARD_PANEL_ID)

    async def refresh(self) -> bool:
        return await self.bot.panels.refresh(RANKING_BOARD_PANEL_ID)

    def unregister(self) -> None:
        self.bot.panels.unregister(RANKING_BOARD_PANEL_ID)

    async def render(self) -> PersistentPanelContent:
        monthly_powers = await self.bot.db.monthly_powers.get_monthly_power_ranking(limit=10)
        star_grades = await self.bot.db.star_grades.get_star_grade_ranking(limit=10)

        monthly_pages = build_power_ranking_pages(
            self.bot,
            monthly_powers,
            title="月間ランキング",
            description=(
                "月間ランキング 現在のTOP10\n\n"
                f"{AsteroidEmoji.TEXT_POWER}: テキストパワー\n"
                f"{AsteroidEmoji.VOICE_POWER}: ボイスパワー\n"
                f"{AsteroidEmoji.ACTION_POWER}: アクションパワー\n"
                f"{AsteroidEmoji.TRANSPARENT}"
            ),
        )
        shard_pages = build_shard_ranking_pages(
            self.bot,
            star_grades,
            title="恒常ランキング",
            description=(
                "恒常ランキング 現在のTOP10\n\n"
                f"{AsteroidEmoji.PRESTIGE}: プレステージ\n"
                f"{AsteroidEmoji.GRADE}: グレード\n"
                f"{AsteroidEmoji.SHARD}: シャード\n"
                f"{AsteroidEmoji.TRANSPARENT}"
            ),
        )

        return PersistentPanelContent(
            embeds=(),
            view=LevelingLayoutView(shard_pages[0], monthly_pages[0], timeout=None),
        )
