from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import discord

from app.common.constants import AsteroidColor
from app.core.bot import AsteroidBot
from app.database.repositories.monthly_powers import MonthlyPowerRankingData
from app.features.leveling.monthly import build_monthly_ranking_views


class FakeAvatar:
    def __init__(self, user_id: int) -> None:
        self.url = f"https://example.com/avatar-{user_id}.png"


class FakeUser:
    def __init__(self, user_id: int) -> None:
        self.display_name = f"User {user_id}"
        self.display_avatar = FakeAvatar(user_id)


class FakeBot:
    def __init__(self) -> None:
        self.users = {user_id: FakeUser(user_id) for user_id in range(1, 11)}

    def get_user(self, user_id: int) -> FakeUser | None:
        return self.users.get(user_id)


def text_contents(item: Any) -> str:
    return "\n".join(child.content for child in item.walk_children() if isinstance(child, discord.ui.TextDisplay))


def test_build_monthly_ranking_views_splits_top10_into_three_messages() -> None:
    now = datetime.now()
    monthly_powers = [
        MonthlyPowerRankingData(user_id, 100, 50, 25, now, now, ranking)
        for ranking, user_id in enumerate(range(1, 11), start=1)
    ]

    views = build_monthly_ranking_views(cast(AsteroidBot, FakeBot()), monthly_powers)

    assert len(views) == 3
    assert "# 月間ランキング発表" in text_contents(views[0])
    assert len(views[0].children) == 1
    assert cast(discord.ui.Container, views[0].children[0]).accent_colour == AsteroidColor.SUCCESS

    assert "# 月間ランキング 1〜5位" in text_contents(views[1])
    assert "### 5位: User 5" in text_contents(views[1])
    assert "# 月間ランキング 6〜10位" in text_contents(views[2])
    assert "### 10位: User 10" in text_contents(views[2])
    assert sum(isinstance(child, discord.ui.Section) for child in views[1].walk_children()) == 5
    assert sum(isinstance(child, discord.ui.Section) for child in views[2].walk_children()) == 5


def test_build_monthly_ranking_views_keeps_empty_second_half_message() -> None:
    now = datetime.now()
    monthly_powers = [
        MonthlyPowerRankingData(user_id, 100, 50, 25, now, now, ranking)
        for ranking, user_id in enumerate(range(1, 4), start=1)
    ]

    views = build_monthly_ranking_views(cast(AsteroidBot, FakeBot()), monthly_powers)

    assert len(views) == 3
    assert "ランキングデータはありません。" in text_contents(views[2])
