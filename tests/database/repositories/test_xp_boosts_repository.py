from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import MetaData, Table, create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.schema import DefaultClause

from app.database.models.xp_boosts import XPBoostModel
from app.database.repositories import xp_boosts


@pytest.mark.asyncio
async def test_expires_boosts(monkeypatch):
    """UTC の期限到達・期限切れだけを削除し、無期限と有効期間内のブースターは残す。"""
    # 機能要件：保存した終了日時を過ぎたブースターを削除する。
    # 非機能要件：DB サーバーのタイムゾーンに依存せず期限を判定する。
    # Given
    now = datetime(2026, 9, 20, 12, tzinfo=UTC)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is UTC
            return now

    monkeypatch.setattr(xp_boosts, "datetime", FixedDatetime)
    engine = create_engine("sqlite://")
    table = cast(Table, XPBoostModel.__table__).to_metadata(MetaData())
    # SQLite では MySQL の ON UPDATE 句を使えないため、テスト用テーブルのデフォルトだけを置き換える。
    table.c.updated_at.server_default = DefaultClause(func.current_timestamp())
    try:
        table.create(engine)
        with Session(engine) as session:

            @asynccontextmanager
            async def session_context():
                yield SimpleNamespace(
                    add=session.add,
                    execute=AsyncMock(side_effect=session.execute),
                    commit=AsyncMock(side_effect=session.commit),
                )

            repository = xp_boosts.XPBoosts(SimpleNamespace(session=session_context))
            base = now.replace(tzinfo=None)
            ends = [None, base - timedelta(seconds=1), base, base + timedelta(seconds=1)]
            for role_id, end in enumerate(ends, start=1):
                await repository.create_xp_boost(role_id, "期間テスト", 200, end)
            assert [
                row.boost_end_time for row in session.scalars(select(XPBoostModel).order_by(XPBoostModel.role_id))
            ] == ends

            # When
            await repository.delete_expired_xp_boosts()

            # Then
            assert list(session.scalars(select(XPBoostModel.role_id).order_by(XPBoostModel.role_id))) == [1, 4]
    finally:
        engine.dispose()
