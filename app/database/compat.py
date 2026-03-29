from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine


def _convert_sql(query: str, params: Sequence[Any] | None = None) -> tuple[str, dict[str, Any]]:
    if not params:
        return query, {}

    sql = query
    bindings: dict[str, Any] = {}
    for index, value in enumerate(params):
        placeholder = f"p{index}"
        sql = sql.replace("%s", f":{placeholder}", 1)
        bindings[placeholder] = value
    return sql, bindings


class CompatCursor:
    def __init__(self, connection: CompatConnection):
        self.connection = connection
        self._result = None

    async def __aenter__(self) -> CompatCursor:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def execute(self, query: str, params: Sequence[Any] | None = None) -> None:
        sql, bindings = _convert_sql(query, params)
        self._result = await self.connection.raw.execute(text(sql), bindings)

    async def executemany(self, query: str, rows: list[Sequence[Any]]) -> None:
        for row in rows:
            await self.execute(query, row)

    async def fetchone(self) -> tuple[Any, ...] | None:
        if self._result is None:
            return None
        row = self._result.fetchone()
        return tuple(row) if row is not None else None

    async def fetchall(self) -> list[tuple[Any, ...]]:
        if self._result is None:
            return []
        return [tuple(row) for row in self._result.fetchall()]


@dataclass
class CompatConnection:
    raw: AsyncConnection

    def cursor(self) -> CompatCursor:
        return CompatCursor(self)

    async def commit(self) -> None:
        await self.raw.commit()

    async def rollback(self) -> None:
        await self.raw.rollback()


class _AcquireContext:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self.raw: AsyncConnection | None = None

    async def __aenter__(self) -> CompatConnection:
        self.raw = await self.engine.connect()
        return CompatConnection(self.raw)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        assert self.raw is not None
        if exc_type is not None:
            await self.raw.rollback()
        await self.raw.close()


class CompatPool:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    def acquire(self) -> _AcquireContext:
        return _AcquireContext(self.engine)
