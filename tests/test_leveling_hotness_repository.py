from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest
from sqlalchemy.dialects import mysql

from app.database.models.leveling_hotness import LevelingHotnessEventModel
from app.database.repositories import DatabaseRepositories
from app.database.repositories.leveling_hotness import (
    DEFAULT_HOTNESS_RANKING_LIMIT,
    HOTNESS_WINDOW,
    LevelingHotness,
    LevelingHotnessRankingData,
)


class FakeResult:
    def __init__(self, rows: list[object] | None = None, *, rowcount: int = 0) -> None:
        self._rows = rows or []
        self.rowcount = rowcount

    def all(self) -> list[object]:
        return self._rows


class FakeSession:
    def __init__(self, results: list[FakeResult] | None = None) -> None:
        self.results = results or []
        self.added: list[object] = []
        self.executed: list[object] = []
        self.commit_count = 0

    def add(self, model: object) -> None:
        self.added.append(model)

    async def execute(self, statement: object) -> FakeResult:
        self.executed.append(statement)
        return self.results.pop(0)

    async def commit(self) -> None:
        self.commit_count += 1


class FakeSessionContext:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    async def __aenter__(self) -> FakeSession:
        return self.session

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


def build_repository(session: FakeSession) -> LevelingHotness:
    db = SimpleNamespace(session=lambda: FakeSessionContext(session))
    return LevelingHotness(db)


@pytest.mark.asyncio
async def test_record_gain_adds_timestamped_event_and_commits() -> None:
    session = FakeSession()
    repository = build_repository(session)
    earned_at = datetime(2026, 6, 12, 3, 0, tzinfo=UTC)

    await repository.record_gain(123, 45, earned_at=earned_at)

    assert session.commit_count == 1
    assert len(session.added) == 1
    event = session.added[0]
    assert isinstance(event, LevelingHotnessEventModel)
    assert event.user_id == 123
    assert event.amount == 45
    assert event.earned_at == datetime(2026, 6, 12, 3, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(("user_id", "amount"), [(0, 1), (1, 0), (-1, 1), (1, -1)])
async def test_record_gain_rejects_non_positive_values(user_id: int, amount: int) -> None:
    session = FakeSession()
    repository = build_repository(session)

    with pytest.raises(ValueError):
        await repository.record_gain(user_id, amount)

    assert session.added == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_get_top_hotness_aggregates_last_24_hours_and_defaults_to_top3() -> None:
    session = FakeSession(
        [
            FakeResult(
                [
                    SimpleNamespace(user_id=10, hotness=500),
                    SimpleNamespace(user_id=20, hotness=300),
                    SimpleNamespace(user_id=30, hotness=100),
                ]
            )
        ]
    )
    repository = build_repository(session)
    now = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)

    result = await repository.get_top_hotness(now=now)

    assert result == [
        LevelingHotnessRankingData(user_id=10, hotness=500),
        LevelingHotnessRankingData(user_id=20, hotness=300),
        LevelingHotnessRankingData(user_id=30, hotness=100),
    ]
    statement = cast(Any, session.executed[0])
    compiled = statement.compile(dialect=mysql.dialect())
    sql = str(compiled)
    assert "sum(leveling_hotness_events.amount)" in sql
    assert "GROUP BY leveling_hotness_events.user_id" in sql
    assert "ORDER BY hotness DESC, leveling_hotness_events.user_id ASC" in sql
    assert compiled.params["earned_at_1"] == datetime(2026, 6, 11, 12, 0)
    assert compiled.params["param_1"] == DEFAULT_HOTNESS_RANKING_LIMIT


@pytest.mark.asyncio
async def test_get_top_hotness_returns_empty_without_query_for_non_positive_limit() -> None:
    session = FakeSession()
    repository = build_repository(session)

    assert await repository.get_top_hotness(limit=0) == []
    assert session.executed == []


@pytest.mark.asyncio
async def test_delete_expired_removes_events_before_24_hour_cutoff() -> None:
    session = FakeSession([FakeResult(rowcount=4)])
    repository = build_repository(session)
    now = datetime(2026, 6, 12, 12, 0)

    deleted_count = await repository.delete_expired(now=now)

    assert deleted_count == 4
    assert session.commit_count == 1
    compiled = cast(Any, session.executed[0]).compile(dialect=mysql.dialect())
    assert compiled.params["earned_at_1"] == now - HOTNESS_WINDOW


def test_hotness_table_has_time_and_user_index() -> None:
    index_columns = {
        tuple(column.name for column in index.columns)
        for index in cast(Any, LevelingHotnessEventModel.__table__).indexes
    }

    assert ("earned_at", "user_id") in index_columns


def test_database_repositories_exposes_leveling_hotness_repository() -> None:
    repositories = DatabaseRepositories()

    assert isinstance(repositories.leveling_hotness, LevelingHotness)
