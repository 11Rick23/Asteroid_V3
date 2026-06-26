from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Any, cast

import pytest
from sqlalchemy.dialects import mysql

from app.database.models.starred_messages import StarredMessageModel
from app.database.repositories.starred_messages import StarredMessages


class FakeResult:
    def __init__(self, *, rowcount: int) -> None:
        self.rowcount = rowcount


class FakeSession:
    def __init__(self, *, rowcount: int = 1) -> None:
        self.rowcount = rowcount
        self.added: list[object] = []
        self.executed: list[object] = []
        self.commit_count = 0
        self.flush_count = 0
        self.refreshed: list[object] = []

    def add(self, model: object) -> None:
        self.added.append(model)

    async def execute(self, statement: object) -> FakeResult:
        self.executed.append(statement)
        return FakeResult(rowcount=self.rowcount)

    async def flush(self) -> None:
        self.flush_count += 1

    async def refresh(self, model: object) -> None:
        self.refreshed.append(model)
        if isinstance(model, StarredMessageModel):
            now = datetime(2026, 6, 26, 1, 0)
            model.created_at = now
            model.updated_at = now

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


def build_repository(session: FakeSession) -> StarredMessages:
    return StarredMessages(FakeDatabase(session))


@pytest.mark.asyncio
async def test_create_returns_dto() -> None:
    """スターボード投稿作成は保存した starred message DTO を返す。"""
    # 機能要件：スターボード投稿作成は保存した内容を DTO として返す。
    # 非機能要件：作成後に flush / refresh して DB 由来の timestamp を DTO に含める。
    # Given
    session = FakeSession()
    repository = build_repository(session)

    # When
    result = await repository.create_starred_message(100, 200, 5, 300, 400)

    # Then
    assert result.starred_message_id == 100
    assert result.starboard_message_id == 200
    assert result.star_amount == 5
    assert result.user_id == 300
    assert result.starred_message_channel_id == 400
    assert result.created_at == datetime(2026, 6, 26, 1, 0)
    assert len(session.added) == 1
    assert session.flush_count == 1
    assert session.refreshed == session.added
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_set_star_amount_uses_update() -> None:
    """星数更新は ORM row 読み取りではなく SQL UPDATE を実行し、更新有無を返す。"""
    # 機能要件：指定 message の star_amount を更新し、更新できたかを返す。
    # 非機能要件：更新は read-modify-write ではなく SQL UPDATE で行う。
    # Given
    session = FakeSession(rowcount=1)
    repository = build_repository(session)

    # When
    updated = await repository.set_star_amount(100, 7)

    # Then
    assert updated is True
    assert session.commit_count == 1
    compiled = cast(Any, session.executed[0]).compile(dialect=mysql.dialect())
    sql = str(compiled)
    assert "UPDATE starred_messages SET star_amount=%s" in sql
    assert "WHERE starred_messages.starred_message_id = %s" in sql
    assert compiled.params["star_amount"] == 7
    assert compiled.params["starred_message_id_1"] == 100


@pytest.mark.asyncio
async def test_set_starboard_message_id_returns_false_for_missing() -> None:
    """存在しない message の starboard message ID 更新では False を返す。"""
    # 機能要件：対象行が存在しない更新は False として呼び出し側へ返す。
    # 非機能要件：missing row でも不要な ORM row 読み取りは行わない。
    # Given
    session = FakeSession(rowcount=0)
    repository = build_repository(session)

    # When
    updated = await repository.set_starboard_message_id(100, 201)

    # Then
    assert updated is False
    assert session.commit_count == 1
    compiled = cast(Any, session.executed[0]).compile(dialect=mysql.dialect())
    sql = str(compiled)
    assert "UPDATE starred_messages SET starboard_message_id=%s" in sql
    assert "WHERE starred_messages.starred_message_id = %s" in sql
    assert compiled.params["starboard_message_id"] == 201
    assert compiled.params["starred_message_id_1"] == 100


@pytest.mark.asyncio
async def test_delete_uses_delete_statement() -> None:
    """スターボード投稿削除は SQL DELETE を実行し、削除有無を返す。"""
    # 機能要件：指定 message の starred message row を削除し、削除できたかを返す。
    # 非機能要件：削除は ORM row 読み取りではなく SQL DELETE で行う。
    # Given
    session = FakeSession(rowcount=1)
    repository = build_repository(session)

    # When
    deleted = await repository.delete_starred_message(100)

    # Then
    assert deleted is True
    assert session.commit_count == 1
    compiled = cast(Any, session.executed[0]).compile(dialect=mysql.dialect())
    sql = str(compiled)
    assert "DELETE FROM starred_messages" in sql
    assert "WHERE starred_messages.starred_message_id = %s" in sql
    assert compiled.params["starred_message_id_1"] == 100
