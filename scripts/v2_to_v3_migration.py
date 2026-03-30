from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
from collections.abc import Sequence

from sqlalchemy import func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.sql.schema import Table

import app.database.models  # noqa: F401
from app.database.base import Base

logger = logging.getLogger(__name__)

TARGET_ONLY_TABLES = {"monthly_action_powers"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Asteroid V2 DB から V3 DB へデータを移行します。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--source-database-url",
        dest="source_database_url",
        help="移行元DBのSQLAlchemy接続URL。未指定なら実行時に入力します",
    )
    parser.add_argument(
        "--target-database-url",
        dest="target_database_url",
        help="移行先DBのSQLAlchemy接続URL。未指定なら実行時に入力します",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="1回のINSERTで転送する最大行数",
    )
    parser.add_argument(
        "--echo",
        action="store_true",
        help="SQLAlchemyのSQLログを有効化します",
    )
    return parser.parse_args()


def prompt_database_url(label: str, provided_value: str | None) -> str:
    if provided_value is not None and provided_value.strip():
        return provided_value.strip()

    value = getpass.getpass(f"{label} DB URL: ").strip()
    if not value:
        raise RuntimeError(f"{label} DB URL が空です。")
    return value


def normalize_database_url(database_url: str) -> str:
    url = make_url(database_url)

    if url.drivername == "mysql":
        return str(url.set(drivername="mysql+aiomysql"))

    if url.get_backend_name() == "mysql" and url.get_driver_name() != "aiomysql":
        raise RuntimeError(
            "MySQL 接続には async ドライバが必要です。 接続URLを 'mysql+aiomysql://...' にしてください。"
        )

    return database_url


def create_engine(database_url: str, echo: bool) -> AsyncEngine:
    return create_async_engine(
        normalize_database_url(database_url),
        echo=echo,
        future=True,
        pool_pre_ping=True,
    )


async def get_table_names(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as conn:
        return await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))


async def create_target_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def count_rows(conn: AsyncConnection, table: Table) -> int:
    return int(await conn.scalar(select(func.count()).select_from(table)) or 0)


async def ensure_target_tables_are_empty(engine: AsyncEngine, tables: Sequence[Table]) -> None:
    async with engine.connect() as conn:
        non_empty_tables: list[str] = []
        for table in tables:
            row_count = await count_rows(conn, table)
            if row_count > 0:
                non_empty_tables.append(f"{table.name} ({row_count} rows)")

    if non_empty_tables:
        raise RuntimeError("移行先DBに既存データがあります。空のDBを指定してください: " + ", ".join(non_empty_tables))


async def copy_table(source_conn: AsyncConnection, target_conn: AsyncConnection, table: Table, batch_size: int) -> int:
    logger.info("Copying table: %s", table.name)
    inserted_rows = 0

    try:
        stream = await source_conn.stream(select(table))
        async for partition in stream.mappings().partitions(batch_size):
            rows = [dict(row) for row in partition]
            if not rows:
                continue
            await target_conn.execute(table.insert(), rows)
            inserted_rows += len(rows)
    except NotImplementedError:
        result = await source_conn.execute(select(table))
        rows = [dict(row) for row in result.mappings().all()]
        if rows:
            await target_conn.execute(table.insert(), rows)
            inserted_rows = len(rows)

    logger.info("Copied table: %s rows=%s", table.name, inserted_rows)
    return inserted_rows


def get_migration_tables() -> list[Table]:
    return [table for table in Base.metadata.sorted_tables if table.name not in TARGET_ONLY_TABLES]


async def migrate(source_database_url: str, target_database_url: str, batch_size: int, echo: bool) -> None:
    if batch_size <= 0:
        raise RuntimeError("--batch-size には 1 以上の値を指定してください。")

    source_engine = create_engine(source_database_url, echo)
    target_engine = create_engine(target_database_url, echo)

    try:
        source_table_names = await get_table_names(source_engine)
        await create_target_tables(target_engine)

        migration_tables = get_migration_tables()
        expected_source_tables = {table.name for table in migration_tables}
        missing_source_tables = sorted(expected_source_tables - source_table_names)
        if missing_source_tables:
            raise RuntimeError("移行元DBに必要なテーブルが不足しています: " + ", ".join(missing_source_tables))

        extra_source_tables = sorted(source_table_names - expected_source_tables)
        if extra_source_tables:
            logger.warning("移行対象外のテーブルを検出しました: %s", ", ".join(extra_source_tables))

        await ensure_target_tables_are_empty(target_engine, migration_tables)

        copied_table_count = 0
        copied_row_count = 0
        async with source_engine.connect() as source_conn, target_engine.begin() as target_conn:
            for table in migration_tables:
                copied_row_count += await copy_table(source_conn, target_conn, table, batch_size)
                copied_table_count += 1

        logger.info(
            "Migration completed: copied_tables=%s copied_rows=%s created_tables=%s",
            copied_table_count,
            copied_row_count,
            len(Base.metadata.sorted_tables),
        )
    finally:
        await source_engine.dispose()
        await target_engine.dispose()


async def async_main() -> None:
    args = parse_args()
    source_database_url = prompt_database_url("source", args.source_database_url)
    target_database_url = prompt_database_url("target", args.target_database_url)
    await migrate(
        source_database_url=source_database_url,
        target_database_url=target_database_url,
        batch_size=args.batch_size,
        echo=args.echo,
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
