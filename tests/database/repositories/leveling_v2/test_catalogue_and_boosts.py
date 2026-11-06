from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.repositories.leveling_v2.boosts import BoostRepository
from app.database.repositories.leveling_v2.catalogue import CatalogueRepository
from app.database.repositories.leveling_v2.locks import MutationGate
from app.features.leveling.domain.boosts import rate_at

NOW = datetime(2026, 10, 15, tzinfo=UTC)


@pytest.mark.asyncio
async def test_installation_guard(sessions: async_sessionmaker[AsyncSession]) -> None:
    """別Guildや開始日時の変更で既存残高の運用先をすり替えない。"""
    # 非機能要件：単一Guildのinstallationを固定し、schema activationは行わない。
    # Given
    repo = CatalogueRepository(sessions, MutationGate())
    first = await repo.install(123, NOW)
    # When / Then
    assert await repo.install(123, NOW) == first
    assert first.generation == 0
    with pytest.raises(ValueError, match="一致"):
        await repo.install(456, NOW)
    with pytest.raises(ValueError, match="一致"):
        await repo.install(123, NOW + timedelta(days=1))


@pytest.mark.asyncio
async def test_channel_history(sessions: async_sessionmaker[AsyncSession]) -> None:
    """最新名を保存し、削除後は最後の名前を保持する。"""
    # 機能要件：古い観測で名称を巻き戻さず、チャンネルを物理削除しない。
    # Given
    repo = CatalogueRepository(sessions, MutationGate())
    await repo.observe_channel(10, "旧名", "text", NOW)
    await repo.observe_channel(10, "新名", "text", NOW + timedelta(seconds=1))
    # When
    await repo.observe_channel(10, "古い観測", "text", NOW)
    final = await repo.observe_channel(10, "新名", "text", NOW + timedelta(seconds=2), deleted=True)
    # Then
    assert final.name == "新名" and final.deleted_at is not None
    assert await repo.get_channel(10) == final


@pytest.mark.asyncio
async def test_boost_history(sessions: async_sessionmaker[AsyncSession]) -> None:
    """同一ロールの予約を重複保存し、取消後も過去時点の率を再現する。"""
    # 機能要件：ブーストは論理取消のみで、操作キーによる再試行で予約を増やさない。
    # Given
    repo = BoostRepository(sessions, MutationGate())
    arguments = {
        "operation_key": "boost-1",
        "actor_id": 99,
        "name": "倍増",
        "role_id": 10,
        "rate_percent": 100,
        "starts_at": NOW,
        "ends_at": None,
        "now": NOW,
    }
    first = await repo.create(**arguments)
    assert await repo.create(**arguments) == first
    second = await repo.create(
        operation_key="boost-2",
        actor_id=99,
        name="追加",
        role_id=10,
        rate_percent=50,
        starts_at=NOW,
        ends_at=None,
        now=NOW,
    )
    # When
    cancelled = await repo.cancel(
        first.boost.boost_id, 0, operation_key="cancel-1", actor_id=99, now=NOW + timedelta(hours=1)
    )
    # Then
    assert cancelled.version == 1
    assert await repo.create(**arguments) == first
    boosts = tuple(row.boost for row in await repo.list(role_id=10))
    assert len(boosts) == 2
    assert rate_at(boosts, {10}, NOW) == 150
    assert rate_at(boosts, {10}, NOW + timedelta(hours=1)) == second.boost.rate_percent
