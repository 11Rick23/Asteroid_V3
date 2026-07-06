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

RANKING_BOARD_PANEL_ID = "ranking_board"
RANKING_BOARD_LIMIT = 3
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
        monthly_powers, star_grades, hotness = await asyncio.gather(
            self.bot.db.monthly_powers.get_monthly_power_ranking(limit=RANKING_BOARD_LIMIT),
            self.bot.db.star_grades.get_star_grade_ranking(limit=RANKING_BOARD_LIMIT),
            self.bot.db.leveling_hotness.get_top_hotness(limit=RANKING_BOARD_LIMIT),
        )

        power_pages = build_power_ranking_pages(
            self.bot,
            monthly_powers,
            title="パワーランキング",
            description=(
                f"月間パワー 現在のTOP{RANKING_BOARD_LIMIT}\n\n"
                f"{AsteroidEmoji.TEXT_POWER}: テキストパワー\n"
                f"{AsteroidEmoji.VOICE_POWER}: ボイスパワー\n"
                f"{AsteroidEmoji.ACTION_POWER}: アクションパワー\n"
                f"{AsteroidEmoji.TRANSPARENT}"
            ),
        )
        shard_pages = build_shard_ranking_pages(
            self.bot,
            star_grades,
            title="シャードランキング",
            description=(
                f"累計シャード 現在のTOP{RANKING_BOARD_LIMIT}\n\n"
                f"{AsteroidEmoji.PRESTIGE}: プレステージ\n"
                f"{AsteroidEmoji.GRADE}: グレード\n"
                f"{AsteroidEmoji.SHARD}: シャード\n"
                f"{AsteroidEmoji.TRANSPARENT}"
            ),
        )
        hotness_container = build_hotness_ranking_container(
            self.bot,
            hotness,
            title="🔥 急上昇ランキング",
            description=f"直近24時間の経験値獲得量 TOP{RANKING_BOARD_LIMIT}",
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
