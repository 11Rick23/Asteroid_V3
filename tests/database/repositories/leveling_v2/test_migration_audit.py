from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import Account
from app.database.repositories.leveling_v2.locks import MutationGate
from app.database.repositories.leveling_v2.migration_audit import MigrationAuditRepository, MigrationItemData

NOW = datetime(2026, 10, 15, tzinfo=UTC)


@pytest.mark.asyncio
async def test_immutable_migration_audit(sessions: async_sessionmaker[AsyncSession]) -> None:
    """原本digestと行キーの重複を防ぎ、監査保存だけでは残高を移行しない。"""
    # 非機能要件：P6の実移行を接続せず、永久台帳の再実行安全性を保証する。
    # Given
    repo = MigrationAuditRepository(sessions, MutationGate())
    run = await repo.prepare(
        source_revision="legacy-test",
        source_digest="a" * 64,
        target_generation=2,
        cutover_at=NOW,
        checksums={"count": 1},
    )
    item = MigrationItemData("star_grades", "1", {"text_shard": "123"}, {"user_id": 1}, NOW)
    # When
    assert await repo.append(run.migration_id, (item,)) == 1
    # Then
    assert await repo.append(run.migration_id, (item,)) == 1
    with pytest.raises(ValueError, match="変更できません"):
        await repo.append(run.migration_id, (replace(item, source_values={"text_shard": "124"}),))
    with pytest.raises(ValueError, match="別の移行要求"):
        await repo.prepare(
            source_revision="legacy-test",
            source_digest="a" * 64,
            target_generation=3,
            cutover_at=NOW,
            checksums={"count": 1},
        )
    async with sessions() as session:
        assert list(await session.scalars(select(Account))) == []
