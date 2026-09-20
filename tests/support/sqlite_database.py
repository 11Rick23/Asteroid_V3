from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy import Integer, MetaData, create_engine, func
from sqlalchemy.orm import Session
from sqlalchemy.schema import DefaultClause

from app.database.base import Base
from app.database.repositories import DatabaseRepositories


class SQLiteDatabase(DatabaseRepositories):
    """外部 DB を使わず repository の保存・rollback を検証するアダプター。"""

    def __init__(self):
        super().__init__()
        self.engine = create_engine("sqlite://")
        metadata = MetaData()
        for source in Base.metadata.tables.values():
            table = source.to_metadata(metadata)
            for column in table.columns:
                column.type = column.type.as_generic()
                if column.primary_key and column.autoincrement and isinstance(column.type, Integer):
                    column.type = Integer()
            if "updated_at" in table.c:
                # MySQL の ON UPDATE 句は SQLite にない。
                table.c.updated_at.server_default = DefaultClause(func.current_timestamp())
        metadata.create_all(self.engine)

    @asynccontextmanager
    async def session(self):
        with Session(self.engine) as session:
            proxy = SimpleNamespace(add=session.add, add_all=session.add_all)
            for name in ("get", "scalar", "scalars", "execute", "flush", "refresh", "commit", "delete", "rollback"):
                setattr(proxy, name, AsyncMock(side_effect=getattr(session, name)))
            yield proxy
