from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.base import Base
from app.database.models.leveling_v2 import LevelingBase

ROOT = Path(__file__).resolve().parents[4]
TEST_URL = "mysql+aiomysql://root@/asteroid_p2_test?unix_socket=/private/tmp/asteroid-p2-mysql/mysql.sock"


@pytest.mark.asyncio
async def test_legacy_schema_unchanged(
    sessions: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """新schemaのdowngrade・再upgradeでも旧表定義・旧データ・旧revisionを変更しない。"""
    # 非機能要件：本番設定を読まず、隔離DBで新旧schemaの並存を検証する。
    # Given
    monkeypatch.setenv("ASTEROID_DATABASE_URL", TEST_URL)
    await asyncio.to_thread(command.upgrade, Config(str(ROOT / "alembic.ini")), "head")
    async with sessions() as session:
        assert await session.scalar(text("SELECT DATABASE()")) == "asteroid_p2_test"
        await session.execute(text("DELETE FROM monthly_powers WHERE user_id=987654321"))
        await session.execute(
            text("INSERT INTO monthly_powers(user_id,text_power,voice_power) VALUES(987654321,77,88)")
        )
        await session.commit()
        original = (await session.execute(text("SELECT * FROM monthly_powers WHERE user_id=987654321"))).one()
        legacy_revision = await session.scalar(text("SELECT version_num FROM alembic_version"))
        ddl = {
            name: (await session.execute(text(f"SHOW CREATE TABLE `{name}`"))).one()[1]
            for name in Base.metadata.tables
        }
    config = Config(str(ROOT / "alembic-leveling-p2.ini"))
    # When
    await asyncio.to_thread(command.downgrade, config, "base")
    async with sessions() as session:
        tables = set(await session.scalars(text("SHOW TABLES")))
        assert not tables.intersection(LevelingBase.metadata.tables)
    await asyncio.to_thread(command.upgrade, config, "head")
    # Then
    async with sessions() as session:
        assert (await session.execute(text("SELECT * FROM monthly_powers WHERE user_id=987654321"))).one() == original
        assert await session.scalar(text("SELECT version_num FROM alembic_version")) == legacy_revision
        assert await session.scalar(text("SELECT version_num FROM alembic_version_leveling_p2")) == "p2_20261101_01"
        for name, expected in ddl.items():
            assert (await session.execute(text(f"SHOW CREATE TABLE `{name}`"))).one()[1] == expected
