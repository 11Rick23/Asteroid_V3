from __future__ import annotations

from datetime import datetime

import discord
import pytest
from sqlalchemy.dialects import mysql

from app.database.models.monthly_powers import MonthlyPowerModel
from app.database.repositories.monthly_powers import MonthlyPowerRankingData, MonthlyPowers
from app.database.repositories.star_grades import StarGradeRankingData
from app.features.leveling.build_send_message import (
    build_power_embed,
    build_power_ranking_embed,
    build_rank_embed,
    total_monthly_power,
)


class FakeAvatar:
    url = "https://example.com/avatar.png"


class FakeUser:
    def __init__(self, user_id: int, display_name: str) -> None:
        self.id = user_id
        self.display_name = display_name
        self.display_avatar = FakeAvatar()


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


def test_build_power_embed_shows_action_power() -> None:
    now = datetime.now()
    user = FakeUser(123, "Alice")
    monthly_power = MonthlyPowerRankingData(123, 100, 50, 25, now, now, 1)

    embed = build_power_embed(user, monthly_power)

    assert len(embed.fields) == 3
    assert embed.fields[2].name == "アクションパワー数"
    assert embed.fields[2].value == "<:_:1488099100518776993> 25"


def test_build_power_ranking_embed_shows_action_power_and_total() -> None:
    now = datetime.now()
    monthly_power = MonthlyPowerRankingData(123, 100, 50, 25, now, now, 1)
    bot = FakeBot({123: FakeUser(123, "Alice")})
    base_embed = discord.Embed(title="Power Ranking")

    embeds = build_power_ranking_embed(bot, [monthly_power], base_embed=base_embed)

    assert len(embeds) == 1
    field = embeds[0].fields[-1]
    assert field.name == "1位: Alice"
    assert "<:_:1488099100518776993> 25" in field.value
    assert "計: 175" in field.value


def test_build_rank_embed_shows_action_power() -> None:
    now = datetime.now()
    user = FakeUser(123, "Alice")
    monthly_power = MonthlyPowerRankingData(123, 100, 50, 25, now, now, 1)
    star_grade = StarGradeRankingData(123, 1, 2, 3, 4, 5, 6, now, now, 2)

    embed = build_rank_embed(user, monthly_power, star_grade)

    assert "<:_:1488099100518776993> 25" in embed.fields[1].value
    assert "175パワー" in embed.fields[1].name


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

    model = await MonthlyPowers(db=None)._get_or_create_monthly_power_model_lock(session, 123)

    assert model is existing_model
    assert len(session.executed_statements) == 1
    compiled = str(session.executed_statements[0].compile(dialect=mysql.dialect()))
    assert "ON DUPLICATE KEY UPDATE" in compiled
