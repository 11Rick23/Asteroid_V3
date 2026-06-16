from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine


def get_alembic_heads(config_path: str | Path = "alembic.ini") -> tuple[str, ...]:
    alembic_config = Config(str(config_path))
    script = ScriptDirectory.from_config(alembic_config)
    return tuple(script.get_heads())


def validate_database_revision(current_heads: tuple[str, ...], expected_heads: tuple[str, ...]) -> None:
    if not expected_heads:
        raise RuntimeError(
            "Alembic の migration head が見つかりません。"
            "`alembic.ini` と `app/database/migrations/versions/` の配置を確認してください。"
        )

    if set(current_heads) == set(expected_heads):
        return

    expected = ", ".join(expected_heads) or "なし"
    current = ", ".join(current_heads) or "なし"
    if not current_heads:
        raise RuntimeError(
            "DB の Alembic revision が記録されていません。"
            f" 既存 DB の場合は `uv run alembic stamp head`、新規 DB の場合は"
            f" `uv run alembic upgrade head` を実行してください。 expected={expected} current={current}"
        )

    raise RuntimeError(
        "DB の Alembic revision が最新ではありません。"
        f" `uv run alembic upgrade head` を実行してください。 expected={expected} current={current}"
    )


def _get_current_heads(connection: Connection) -> tuple[str, ...]:
    migration_context = MigrationContext.configure(connection)
    return tuple(migration_context.get_current_heads())


async def ensure_database_revision_is_current(engine: AsyncEngine) -> None:
    expected_heads = get_alembic_heads()
    async with engine.connect() as connection:
        current_heads = await connection.run_sync(_get_current_heads)
    validate_database_revision(current_heads, expected_heads)
