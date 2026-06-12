from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import discord
import pytest
from sqlalchemy.dialects import mysql
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bot import AsteroidBot
from app.database.models.monthly_powers import MonthlyPowerModel
from app.database.repositories.monthly_powers import MonthlyPowerRankingData, MonthlyPowers
from app.database.repositories.star_grades import StarGradeRankingData
from app.features.leveling.build_send_message import (
    build_power_ranking_pages,
    build_power_view,
    build_rank_view,
    build_shard_ranking_pages,
    total_monthly_power,
)


class FakeAvatar:
    def __init__(self, user_id: int) -> None:
        self.url = f"https://example.com/avatar-{user_id}.png"


class FakeUser:
    def __init__(self, user_id: int, display_name: str) -> None:
        self.id = user_id
        self.display_name = display_name
        self.display_avatar = FakeAvatar(user_id)


class FakeBot:
    def __init__(self, users: dict[int, FakeUser]) -> None:
        self.users = users

    def get_user(self, user_id: int) -> FakeUser | None:
        return self.users.get(user_id)


class FakeAsyncSession:
    def __init__(self, scalar_results: list[MonthlyPowerModel | None]) -> None:
        self.scalar_results = scalar_results
        self.executed_statements: list[object] = []

    async def scalar(self, _: object) -> MonthlyPowerModel | None:
        return self.scalar_results.pop(0)

    async def execute(self, statement: object) -> None:
        self.executed_statements.append(statement)


def test_total_monthly_power_includes_action_power() -> None:
    now = datetime.now()
    monthly_power = MonthlyPowerRankingData(123, 100, 50, 25, now, now, 1)

    assert total_monthly_power(monthly_power) == 175


def text_contents(item: Any) -> str:
    return "\n".join(
        child.content for child in item.walk_children() if isinstance(child, discord.ui.TextDisplay)
    )


def test_build_power_view_shows_action_power() -> None:
    now = datetime.now()
    user = FakeUser(123, "Alice")
    monthly_power = MonthlyPowerRankingData(123, 100, 50, 25, now, now, 1)

    view = build_power_view(cast(discord.abc.User, user), monthly_power)
    content = text_contents(view)

    assert view.has_components_v2()
    assert "### アクションパワー数" in content
    assert "<:_:1488099100518776993> 25" in content


def test_build_power_ranking_page_shows_action_power_and_total() -> None:
    now = datetime.now()
    monthly_power = MonthlyPowerRankingData(123, 100, 50, 25, now, now, 1)
    bot = FakeBot({123: FakeUser(123, "Alice")})
    pages = build_power_ranking_pages(
        cast(AsteroidBot, bot),
        [monthly_power],
        title="Power Ranking",
        description="description",
    )
    content = text_contents(pages[0])

    assert len(pages) == 1
    assert "### 1位: Alice" in content
    assert "<:_:1488099100518776993> 25" in content
    assert "計: 175" in content
    sections = [child for child in pages[0].children if isinstance(child, discord.ui.Section)]
    assert len(sections) == 1
    thumbnail = cast(discord.ui.Thumbnail, sections[0].accessory)
    assert thumbnail.media.url == "https://example.com/avatar-123.png"


def test_build_power_ranking_page_separates_users_and_shows_each_avatar() -> None:
    now = datetime.now()
    monthly_powers = [
        MonthlyPowerRankingData(123, 100, 50, 25, now, now, 1),
        MonthlyPowerRankingData(456, 90, 40, 20, now, now, 2),
    ]
    bot = FakeBot(
        {
            123: FakeUser(123, "Alice"),
            456: FakeUser(456, "Bob"),
        }
    )

    page = build_power_ranking_pages(
        cast(AsteroidBot, bot),
        monthly_powers,
        title="Power Ranking",
        description="description",
    )[0]

    sections = [child for child in page.children if isinstance(child, discord.ui.Section)]
    separators = [child for child in page.children if isinstance(child, discord.ui.Separator)]
    thumbnails = [cast(discord.ui.Thumbnail, section.accessory).media.url for section in sections]

    assert len(sections) == 2
    assert len(separators) == 1
    assert thumbnails == [
        "https://example.com/avatar-123.png",
        "https://example.com/avatar-456.png",
    ]


def test_build_shard_ranking_page_separates_users_and_shows_each_avatar() -> None:
    now = datetime.now()
    star_grades = [
        StarGradeRankingData(123, 1, 2, 3, 4, 5, 6, now, now, 1),
        StarGradeRankingData(456, 2, 3, 4, 5, 6, 7, now, now, 2),
    ]
    bot = FakeBot(
        {
            123: FakeUser(123, "Alice"),
            456: FakeUser(456, "Bob"),
        }
    )

    page = build_shard_ranking_pages(
        cast(AsteroidBot, bot),
        star_grades,
        title="Shard Ranking",
        description="description",
    )[0]

    sections = [child for child in page.children if isinstance(child, discord.ui.Section)]
    separators = [child for child in page.children if isinstance(child, discord.ui.Separator)]
    thumbnails = [cast(discord.ui.Thumbnail, section.accessory).media.url for section in sections]

    assert len(sections) == 2
    assert len(separators) == 1
    assert thumbnails == [
        "https://example.com/avatar-123.png",
        "https://example.com/avatar-456.png",
    ]


def test_build_rank_view_shows_action_power() -> None:
    now = datetime.now()
    user = FakeUser(123, "Alice")
    monthly_power = MonthlyPowerRankingData(123, 100, 50, 25, now, now, 1)
    star_grade = StarGradeRankingData(123, 1, 2, 3, 4, 5, 6, now, now, 2)

    view = build_rank_view(cast(discord.abc.User, user), monthly_power, star_grade)
    content = text_contents(view)

    assert view.has_components_v2()
    assert "<:_:1488099100518776993> 25" in content
    assert "175パワー" in content


def test_monthly_power_aggregated_subquery_references_action_power_table() -> None:
    compiled = str(MonthlyPowers._aggregated_subquery().select().compile(dialect=mysql.dialect()))

    assert "monthly_action_powers" in compiled
    assert "action_power" in compiled
    assert "coalesce" in compiled.lower()


def test_monthly_power_non_ranking_query_does_not_include_rank_window() -> None:
    compiled = str(MonthlyPowers._aggregated_subquery(include_ranking=False).select().compile(dialect=mysql.dialect()))

    assert "monthly_action_powers" in compiled
    assert "rank()" not in compiled.lower()


@pytest.mark.asyncio
async def test_get_or_create_monthly_power_model_lock_uses_mysql_upsert_for_missing_row() -> None:
    existing_model = MonthlyPowerModel(user_id=123, text_power=0, voice_power=0)
    session = FakeAsyncSession([None, existing_model])

    model = await MonthlyPowers(db=None)._get_or_create_monthly_power_model_lock(cast(AsyncSession, session), 123)

    assert model is existing_model
    assert len(session.executed_statements) == 1
    compiled = str(cast(Any, session.executed_statements[0]).compile(dialect=mysql.dialect()))
    assert "ON DUPLICATE KEY UPDATE" in compiled
