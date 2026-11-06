from __future__ import annotations

from datetime import UTC, datetime

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.leveling_migrations.compare import compare_server_default
from app.database.models.leveling_v2 import Event, LevelingBase, VoicePending
from app.database.repositories.leveling_v2 import LevelingRepository, MessageAward, MutationGate
from app.database.repositories.leveling_v2.voice_state import Checkpoint
from app.features.leveling.domain.numbers import MAX_AMOUNT

NOW = datetime(2026, 10, 15, tzinfo=UTC)


@pytest.mark.asyncio
async def test_migration_matches_metadata(sessions: async_sessionmaker[AsyncSession]) -> None:
    """Alembicで作成したMySQL schemaとモデルの型・制約・索引が一致する。"""
    # 非機能要件：手書きモデルだけでなく実upgrade結果の整合性を検証する。
    # Given
    async with sessions() as session:
        connection = await session.connection()
        # When
        diff = await connection.run_sync(
            lambda sync: compare_metadata(
                MigrationContext.configure(
                    sync,
                    opts={
                        "compare_type": True,
                        "compare_server_default": compare_server_default,
                        "include_object": lambda obj, name, kind, reflected, compare_to: (
                            kind != "table" or name in LevelingBase.metadata.tables
                        ),
                    },
                ),
                LevelingBase.metadata,
            )
        )
    # Then
    assert diff == []


@pytest.mark.asyncio
async def test_decimal_boundary(sessions: async_sessionmaker[AsyncSession]) -> None:
    """DECIMAL(65,0)最大整数を正確に保存し、次の加算は全txを拒否する。"""
    # 非機能要件：floatやDecimal contextで最大値を丸めず、overflowを部分commitしない。
    # Given
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    await repo.award_message(MessageAward(1, 1, "text", NOW, NOW, MAX_AMOUNT))
    # When / Then
    account = await repo.get_account(1)
    assert account is not None and account.text_shard == MAX_AMOUNT
    with pytest.raises(ValueError):
        await repo.award_message(MessageAward(2, 1, "text", NOW, NOW, 1))
    async with sessions() as session:
        assert len(list(await session.scalars(select(Event)))) == 1
        with pytest.raises(DBAPIError):
            await session.execute(
                text("UPDATE leveling_accounts SET text_shard=:value WHERE user_id=1"), {"value": str(MAX_AMOUNT + 1)}
            )
        await session.rollback()
    assert await repo.get_account(1) == account


@pytest.mark.asyncio
async def test_foreign_key_and_check(sessions: async_sessionmaker[AsyncSession]) -> None:
    """存在しないユーザー参照と片側NULLのprepared値をMySQL制約で拒否する。"""
    # 非機能要件：Repository外の不正書込みでも内部参照と準備状態を壊さない。
    # Given
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    await repo.checkpoint(Checkpoint(1, None, None, "epoch", "tracking", NOW, None))
    # When / Then
    async with sessions() as session:
        session.add(VoicePending(user_id=999, month_period_id=999, origin="native"))
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()
        with pytest.raises(DBAPIError):
            await session.execute(text("UPDATE leveling_voice_state SET prepared_grant_seq=1 WHERE user_id=1"))
        await session.rollback()
