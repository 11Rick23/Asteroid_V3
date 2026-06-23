from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from app.core.bot import AsteroidBot
from app.database.repositories.leveling_hotness import LevelingHotnessRankingData
from app.database.repositories.monthly_powers import MonthlyPowerRankingData
from app.database.repositories.star_grades import StarGradeRankingData
from app.features.leveling.ranking_board import (
    RANKING_BOARD_LIMIT,
    RANKING_BOARD_OFFLINE_DESCRIPTION,
    RANKING_BOARD_PANEL_ID,
    RankingBoardPanel,
)


class FakePanelManager:
    def __init__(self) -> None:
        self.registrations: list[tuple[str, int, object, str]] = []
        self.initialized: list[str] = []
        self.refreshed: list[str] = []
        self.unregistered: list[str] = []

    def register(self, panel_id: str, channel_id: int, render: object, *, offline_description: str) -> None:
        self.registrations.append((panel_id, channel_id, render, offline_description))

    async def initialize(self, panel_id: str) -> bool:
        self.initialized.append(panel_id)
        return True

    async def refresh(self, panel_id: str) -> bool:
        self.refreshed.append(panel_id)
        return True

    def unregister(self, panel_id: str) -> None:
        self.unregistered.append(panel_id)


class FakeRankingRepository:
    def __init__(self, rankings: list[Any]) -> None:
        self.rankings = rankings
        self.limits: list[int] = []

    async def get_monthly_power_ranking(self, *, limit: int) -> list[Any]:
        self.limits.append(limit)
        return self.rankings

    async def get_star_grade_ranking(self, *, limit: int) -> list[Any]:
        self.limits.append(limit)
        return self.rankings


class FakeHotnessRepository:
    def __init__(self, rankings: list[LevelingHotnessRankingData]) -> None:
        self.rankings = rankings
        self.limits: list[int] = []

    async def get_top_hotness(self, *, limit: int) -> list[LevelingHotnessRankingData]:
        self.limits.append(limit)
        return self.rankings


class FakeAvatar:
    def __init__(self, user_id: int) -> None:
        self.url = f"https://example.com/avatar-{user_id}.png"


class FakeUser:
    def __init__(self, user_id: int) -> None:
        self.display_name = f"User {user_id}"
        self.display_avatar = FakeAvatar(user_id)


def build_panel(
    *,
    monthly_rankings: list[MonthlyPowerRankingData] | None = None,
    shard_rankings: list[StarGradeRankingData] | None = None,
    hotness_rankings: list[LevelingHotnessRankingData] | None = None,
) -> tuple[
    RankingBoardPanel,
    FakePanelManager,
    FakeRankingRepository,
    FakeRankingRepository,
    FakeHotnessRepository,
]:
    panels = FakePanelManager()
    monthly_powers = FakeRankingRepository(monthly_rankings or [])
    star_grades = FakeRankingRepository(shard_rankings or [])
    leveling_hotness = FakeHotnessRepository(hotness_rankings or [])
    users = {user_id: FakeUser(user_id) for user_id in range(1, 10)}
    bot = cast(
        AsteroidBot,
        SimpleNamespace(
            panels=panels,
            config=SimpleNamespace(leveling=SimpleNamespace(ranking_board_channel_id=200)),
            db=SimpleNamespace(
                monthly_powers=monthly_powers,
                star_grades=star_grades,
                leveling_hotness=leveling_hotness,
            ),
            get_user=users.get,
        ),
    )
    return RankingBoardPanel(bot), panels, monthly_powers, star_grades, leveling_hotness


@pytest.mark.asyncio
async def test_ranking_board_panel_registers_and_uses_common_manager() -> None:
    panel, panels, _, _, _ = build_panel()

    assert panels.registrations == [(RANKING_BOARD_PANEL_ID, 200, panel.render, RANKING_BOARD_OFFLINE_DESCRIPTION)]
    assert await panel.initialize() is True
    assert await panel.refresh() is True
    panel.unregister()

    assert panels.initialized == [RANKING_BOARD_PANEL_ID]
    assert panels.refreshed == [RANKING_BOARD_PANEL_ID]
    assert panels.unregistered == [RANKING_BOARD_PANEL_ID]


@pytest.mark.asyncio
async def test_ranking_board_panel_renders_empty_rankings() -> None:
    panel, _, monthly_powers, star_grades, leveling_hotness = build_panel()

    content = await panel.render()

    assert content.embeds == ()
    assert isinstance(content.view, discord.ui.LayoutView)
    assert content.view.has_components_v2()
    assert len(content.view.children) == 3
    texts = [child.content for child in content.view.walk_children() if isinstance(child, discord.ui.TextDisplay)]
    assert any("# シャードランキング" in text for text in texts)
    assert any("# パワーランキング" in text for text in texts)
    assert any("# 🔥 急上昇ランキング" in text for text in texts)
    assert monthly_powers.limits == [RANKING_BOARD_LIMIT]
    assert star_grades.limits == [RANKING_BOARD_LIMIT]
    assert leveling_hotness.limits == [RANKING_BOARD_LIMIT]


@pytest.mark.asyncio
async def test_ranking_board_panel_renders_three_top3_containers_with_avatars() -> None:
    now = datetime.now()
    panel, _, _, _, _ = build_panel(
        monthly_rankings=[
            MonthlyPowerRankingData(user_id, 100, 50, 25, now, now, ranking)
            for ranking, user_id in enumerate(range(1, 4), start=1)
        ],
        shard_rankings=[
            StarGradeRankingData(user_id, 1, 2, 3, 4, 5, 6, now, now, ranking)
            for ranking, user_id in enumerate(range(4, 7), start=1)
        ],
        hotness_rankings=[
            LevelingHotnessRankingData(user_id, 1000 - ranking)
            for ranking, user_id in enumerate(range(7, 10), start=1)
        ],
    )

    content = await panel.render()

    assert content.view is not None
    assert len(content.view.children) == 3
    sections = [child for child in content.view.walk_children() if isinstance(child, discord.ui.Section)]
    separators = [child for child in content.view.walk_children() if isinstance(child, discord.ui.Separator)]
    thumbnails = [child for child in content.view.walk_children() if isinstance(child, discord.ui.Thumbnail)]
    assert len(sections) == 9
    assert len(separators) == 6
    assert len(thumbnails) == 9
