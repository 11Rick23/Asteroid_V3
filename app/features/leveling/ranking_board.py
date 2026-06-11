from __future__ import annotations

import discord

from app.common.constants import AsteroidColor, AsteroidEmoji
from app.common.persistent_panels import PersistentPanelContent
from app.core.bot import AsteroidBot
from app.features.leveling.build_send_message import (
    build_power_ranking_embed,
    build_shard_ranking_embed,
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

        monthly_base = discord.Embed(
            title="月間ランキング",
            description="月間ランキング 現在のTOP10\n\n"
            f"{AsteroidEmoji.TEXT_POWER}: テキストパワー\n"
            f"{AsteroidEmoji.VOICE_POWER}: ボイスパワー\n"
            f"{AsteroidEmoji.ACTION_POWER}: アクションパワー\n"
            f"{AsteroidEmoji.TRANSPARENT}",
            color=AsteroidColor.INFO,
        )
        shard_base = discord.Embed(
            title="恒常ランキング",
            description="恒常ランキング 現在のTOP10\n\n"
            f"{AsteroidEmoji.PRESTIGE}: プレステージ\n"
            f"{AsteroidEmoji.GRADE}: グレード\n"
            f"{AsteroidEmoji.SHARD}: シャード\n"
            f"{AsteroidEmoji.TRANSPARENT}",
            color=AsteroidColor.INFO,
        )
        monthly_embeds = build_power_ranking_embed(self.bot, monthly_powers, monthly_base)
        shard_embeds = build_shard_ranking_embed(self.bot, star_grades, shard_base)

        return PersistentPanelContent(
            embeds=(
                shard_embeds[0] if shard_embeds else shard_base,
                monthly_embeds[0] if monthly_embeds else monthly_base,
            )
        )
