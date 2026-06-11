from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from app.core.bot import AsteroidBot
from app.features.leveling.ranking_board import RANKING_BOARD_PANEL_ID, RankingBoardPanel


class FakePanelManager:
    def __init__(self) -> None:
        self.registrations: list[tuple[str, int, object]] = []
        self.initialized: list[str] = []
        self.refreshed: list[str] = []
        self.unregistered: list[str] = []

    def register(self, panel_id: str, channel_id: int, render: object) -> None:
        self.registrations.append((panel_id, channel_id, render))

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


def build_panel() -> tuple[RankingBoardPanel, FakePanelManager, FakeRankingRepository, FakeRankingRepository]:
    panels = FakePanelManager()
    monthly_powers = FakeRankingRepository([])
    star_grades = FakeRankingRepository([])
    bot = cast(
        AsteroidBot,
        SimpleNamespace(
            panels=panels,
            config=SimpleNamespace(leveling=SimpleNamespace(ranking_board_channel_id=200)),
            db=SimpleNamespace(monthly_powers=monthly_powers, star_grades=star_grades),
        ),
    )
    return RankingBoardPanel(bot), panels, monthly_powers, star_grades


@pytest.mark.asyncio
async def test_ranking_board_panel_registers_and_uses_common_manager() -> None:
    panel, panels, _, _ = build_panel()

    assert panels.registrations == [(RANKING_BOARD_PANEL_ID, 200, panel.render)]
    assert await panel.initialize() is True
    assert await panel.refresh() is True
    panel.unregister()

    assert panels.initialized == [RANKING_BOARD_PANEL_ID]
    assert panels.refreshed == [RANKING_BOARD_PANEL_ID]
    assert panels.unregistered == [RANKING_BOARD_PANEL_ID]


@pytest.mark.asyncio
async def test_ranking_board_panel_renders_empty_rankings() -> None:
    panel, _, monthly_powers, star_grades = build_panel()

    content = await panel.render()

    assert [embed.title for embed in content.embeds] == ["恒常ランキング", "月間ランキング"]
    assert content.view is None
    assert monthly_powers.limits == [10]
    assert star_grades.limits == [10]
