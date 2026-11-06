from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.models.leveling_v2 import LevelingBase


@pytest_asyncio.fixture
async def sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """専用socket・固定名の使い捨てDB以外へ接続しない。"""
    if os.environ.get("ASTEROID_P2_MYSQL_TEST") != "1":
        pytest.skip("隔離MySQL検証にはASTEROID_P2_MYSQL_TEST=1が必要です")
    engine = create_async_engine(
        "mysql+aiomysql://root@/asteroid_p2_test?unix_socket=/private/tmp/asteroid-p2-mysql/mysql.sock",
        isolation_level="REPEATABLE READ",
    )
    try:
        async with engine.begin() as connection:
            assert await connection.scalar(text("SELECT DATABASE()")) == "asteroid_p2_test"
            await connection.run_sync(LevelingBase.metadata.drop_all)
            await connection.execute(text("DROP TABLE IF EXISTS alembic_version_leveling_p2"))
        config = Config(str(Path(__file__).resolve().parents[4] / "alembic-leveling-p2.ini"))
        await asyncio.to_thread(command.upgrade, config, "head")
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()
