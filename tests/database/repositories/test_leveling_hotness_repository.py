from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from typing import Any, cast

import pytest
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import DefaultClause

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

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None


class FakeDatabase:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    def session(self) -> FakeSessionContext:
        return FakeSessionContext(self._session)


def build_repository(session: FakeSession) -> LevelingHotness:
    return LevelingHotness(FakeDatabase(session))


@pytest.mark.asyncio
async def test_record_gain_commits_timestamped_event() -> None:
    """hotness event を UTC 指定時刻から naive datetime に揃えて保存し commit する。"""
    # 機能要件：ユーザー ID、増分、獲得時刻を hotness event として保存する。
    # 非機能要件：repository 単体の record_gain は自分で commit する。
    # Given
    session = FakeSession()
    repository = build_repository(session)
    earned_at = datetime(2026, 6, 12, 3, 0, tzinfo=UTC)

    # When
    await repository.record_gain(123, 45, earned_at=earned_at)

    # Then
    assert session.commit_count == 1
    assert len(session.added) == 1
    event = session.added[0]
    assert isinstance(event, LevelingHotnessEventModel)
    assert event.user_id == 123
    assert event.amount == 45
    assert event.earned_at == datetime(2026, 6, 12, 3, 0)


@pytest.mark.asyncio
async def test_record_gain_in_session_does_not_commit() -> None:
    """既存 transaction 内の hotness 記録は受け取った session を使い commit しない。"""
    # 機能要件：in_session variant でも hotness event を保存する。
    # 非機能要件：外側 transaction の commit 境界を repository helper が奪わない。
    # Given
    session = FakeSession()
    repository = build_repository(session)

    # When
    await repository.record_gain_in_session(
        cast(Any, session),
        123,
        45,
        earned_at=datetime(2026, 6, 12, 3, 0, tzinfo=UTC),
    )

    # Then
    assert session.commit_count == 0
    assert len(session.added) == 1
    event = session.added[0]
    assert isinstance(event, LevelingHotnessEventModel)
    assert event.user_id == 123
    assert event.amount == 45
    assert event.earned_at == datetime(2026, 6, 12, 3, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize(("user_id", "amount"), [(0, 1), (1, 0), (-1, 1), (1, -1)])
async def test_record_gain_rejects_non_positive(user_id: int, amount: int) -> None:
    """user_id と amount が正でない hotness event は保存しない。"""
    # 非機能要件：不正な user_id / amount では DB へ副作用を発生させない。
    # Given
    session = FakeSession()
    repository = build_repository(session)

    # When / Then
    with pytest.raises(ValueError):
        await repository.record_gain(user_id, amount)

    assert session.added == []
    assert session.commit_count == 0


@pytest.mark.asyncio
async def test_get_top_hotness_aggregates_window() -> None:
    """直近 24 時間の hotness を user ごとに集計し、既定件数で順位 DTO を返す。"""
    # 機能要件：直近 window の hotness 合計を降順、同点 user ID 昇順で返す。
    # 非機能要件：既定 limit を SQL に渡し、window 境界を naive datetime で比較する。
    # Given
    session = FakeSession([
        FakeResult([
            FakeRow(user_id=10, hotness=500),
            FakeRow(user_id=20, hotness=300),
            FakeRow(user_id=30, hotness=100),
        ])
    ])
    repository = build_repository(session)
    now = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)

    # When
    result = await repository.get_top_hotness(now=now)

    # Then
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
async def test_get_top_hotness_skips_non_positive_limit() -> None:
    """limit が正でない場合は query せず空のランキングを返す。"""
    # 機能要件：limit が 0 以下のランキング取得は空リストを返す。
    # 非機能要件：無効 limit では DB query を発行しない。
    # Given
    session = FakeSession()
    repository = build_repository(session)

    # When / Then
    assert await repository.get_top_hotness(limit=0) == []
    assert session.executed == []


@pytest.mark.asyncio
async def test_delete_expired_removes_events_before_cutoff() -> None:
    """保存期間外の hotness event を削除し、削除件数を返す。"""
    # 機能要件：直近 window より古い hotness event を削除件数付きで返す。
    # 非機能要件：削除処理は repository 内で commit する。
    # Given
    session = FakeSession([FakeResult(rowcount=4)])
    repository = build_repository(session)
    now = datetime(2026, 6, 12, 12, 0)

    # When
    deleted_count = await repository.delete_expired(now=now)

    # Then
    assert deleted_count == 4
    assert session.commit_count == 1
    compiled = cast(Any, session.executed[0]).compile(dialect=mysql.dialect())
    assert compiled.params["earned_at_1"] == now - HOTNESS_WINDOW


def test_hotness_table_has_time_and_user_index() -> None:
    """hotness ranking query 用の earned_at/user_id index を持つ。"""
    # 非機能要件：直近 window の user 別集計に使う複合 index を定義する。
    # Given / When
    indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in cast(Any, LevelingHotnessEventModel.__table__).indexes
    }

    # Then
    assert indexes["idx_leveling_hotness_events_earned_at_user_id"] == ("earned_at", "user_id")


def test_hotness_earned_at_uses_database_default() -> None:
    """hotness event の earned_at は DB 側の現在時刻 default を持つ。"""
    # 非機能要件：明示時刻なしの INSERT でも DB 側で獲得時刻を補完できる。
    # Given / When
    default = cast(Any, LevelingHotnessEventModel.__table__).c.earned_at.server_default

    # Then
    assert isinstance(default, DefaultClause)
    assert str(default.arg) == "CURRENT_TIMESTAMP"


def test_database_repositories_exposes_leveling_hotness() -> None:
    """DatabaseRepositories から leveling hotness repository を利用できる。"""
    # 機能要件：DB repository 集約は leveling_hotness repository を公開する。
    # Given / When
    repositories = DatabaseRepositories()

    # Then
    assert isinstance(repositories.leveling_hotness, LevelingHotness)


class FakeRow:
    def __init__(self, *, user_id: int, hotness: int) -> None:
        self.user_id = user_id
        self.hotness = hotness
