"""P2隔離検証専用。既存BotのAlembic headと設定ファイルを変更しない。"""

from __future__ import annotations

import asyncio
import os

from alembic import context
from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.database.leveling_migrations.compare import compare_server_default
from app.database.models.leveling_v2 import LevelingBase

TEST_URL = "mysql+aiomysql://root@/asteroid_p2_test?unix_socket=/private/tmp/asteroid-p2-mysql/mysql.sock"


def migrate(connection: Connection) -> None:
    if connection.scalar(text("SELECT DATABASE()")) != "asteroid_p2_test":
        raise RuntimeError("P2テスト用DB以外へのmigrationは禁止です")
    context.configure(
        connection=connection,
        target_metadata=LevelingBase.metadata,
        version_table="alembic_version_leveling_p2",
        compare_server_default=compare_server_default,
    )
    with context.begin_transaction():
        context.run_migrations()
    connection.commit()


async def online() -> None:
    if os.environ.get("ASTEROID_P2_MYSQL_TEST") != "1":
        raise RuntimeError("隔離MySQL検証にはASTEROID_P2_MYSQL_TEST=1が必要です")
    engine = create_async_engine(TEST_URL, poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(migrate)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=TEST_URL,
        target_metadata=LevelingBase.metadata,
        version_table="alembic_version_leveling_p2",
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(online())
