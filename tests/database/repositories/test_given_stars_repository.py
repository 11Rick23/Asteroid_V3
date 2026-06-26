from __future__ import annotations

from types import TracebackType
from typing import Any, cast

import pytest
from sqlalchemy.dialects import mysql

from app.database.repositories.given_stars import GivenStars


class FakeSession:
    def __init__(self) -> None:
        self.executed: list[object] = []
        self.commit_count = 0

    async def execute(self, statement: object) -> None:
        self.executed.append(statement)

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


def build_repository(session: FakeSession) -> GivenStars:
    return GivenStars(FakeDatabase(session))


@pytest.mark.asyncio
async def test_add_given_star_uses_upsert() -> None:
    """付与済みスター加算は未作成なら作成し、既存なら SQL 側で加算する。"""
    # 機能要件：given_stars が未作成でも add_given_star だけで加算できる。
    # 非機能要件：既存行の加算は read-modify-write ではなく MySQL upsert で行う。
    # Given
    session = FakeSession()
    repository = build_repository(session)

    # When
    await repository.add_given_star(123, 2)

    # Then
    assert session.commit_count == 1
    assert len(session.executed) == 1
    compiled = cast(Any, session.executed[0]).compile(dialect=mysql.dialect())
    sql = str(compiled)
    assert "INSERT INTO given_stars" in sql
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert "given_star_amount = (given_stars.given_star_amount + %s)" in sql
    assert compiled.params["user_id"] == 123
    assert compiled.params["given_star_amount"] == 2


@pytest.mark.asyncio
async def test_create_given_star_uses_same_upsert_path() -> None:
    """create_given_star も競合時は SQL 側加算にフォールバックする。"""
    # 機能要件：create_given_star は指定量の given star を保存する。
    # 非機能要件：同時作成競合では duplicate error ではなく upsert として扱う。
    # Given
    session = FakeSession()
    repository = build_repository(session)

    # When
    await repository.create_given_star(123, 3)

    # Then
    assert session.commit_count == 1
    compiled = cast(Any, session.executed[0]).compile(dialect=mysql.dialect())
    assert "ON DUPLICATE KEY UPDATE" in str(compiled)
    assert compiled.params["user_id"] == 123
    assert compiled.params["given_star_amount"] == 3


@pytest.mark.asyncio
async def test_remove_given_star_uses_atomic_update() -> None:
    """付与済みスター減算は SQL 側で 0 下限つきの atomic update を行う。"""
    # 機能要件：指定ユーザーの given star を指定量だけ減算する。
    # 非機能要件：減算は read-modify-write ではなく SQL の atomic update で行い、負数にしない。
    # Given
    session = FakeSession()
    repository = build_repository(session)

    # When
    await repository.remove_given_star(123, 2)

    # Then
    assert session.commit_count == 1
    assert len(session.executed) == 1
    compiled = cast(Any, session.executed[0]).compile(dialect=mysql.dialect())
    sql = str(compiled)
    assert "UPDATE given_stars SET given_star_amount=greatest(given_stars.given_star_amount - %s, %s)" in sql
    assert "WHERE given_stars.user_id = %s" in sql
    assert compiled.params["given_star_amount_1"] == 2
    assert compiled.params["greatest_1"] == 0
    assert compiled.params["user_id_1"] == 123
