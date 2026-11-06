from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import PeriodChannel, PeriodUser
from app.database.repositories.leveling_v2 import CatalogueRepository, LevelingRepository, MessageAward, MutationGate
from app.database.repositories.leveling_v2.history_queries import HistoryRepository
from app.database.repositories.leveling_v2.maintenance import MaintenanceRepository
from app.database.repositories.leveling_v2.retention import RetentionRepository
from app.features.leveling.domain.boosts import Boost

NOW = datetime(2026, 10, 15, tzinfo=UTC)


@pytest.mark.asyncio
async def test_history_and_filters(sessions: async_sessionmaker[AsyncSession]) -> None:
    """user/channel/time/kind/bonus条件をANDし、同時刻の履歴を重複なくページングする。"""
    # 機能要件：チャンネルJOINの多重行を返さず、受信時刻と獲得時刻の検索を区別する。
    # Given
    gate = MutationGate()
    repo = LevelingRepository(sessions, gate=gate, coverage_start_at=NOW)
    catalogue = CatalogueRepository(sessions, gate)
    for channel in (10, 11):
        await catalogue.observe_channel(channel, str(channel), "text", NOW)
    await repo.award_message(MessageAward(1, 1, "text", NOW, NOW, 10, channel_id=10))
    await repo.award_message(
        MessageAward(
            2, 1, "text", NOW, NOW, 10, channel_id=10, boosts=(Boost(1, 100, 100, NOW),), role_ids=frozenset({100})
        )
    )
    await repo.award_message(MessageAward(3, 1, "text", NOW, NOW, 10, channel_id=11))
    await repo.award_message(MessageAward(4, 2, "text", NOW, NOW, 10, channel_id=10))
    await repo.award_message(MessageAward(5, 1, "action", NOW, NOW, 10))
    history = HistoryRepository(sessions)
    # When
    first = await history.events(
        NOW, NOW + timedelta(days=1), as_of=NOW, user_id=1, channel_id=10, kind="text", limit=1
    )
    second = await history.events(
        NOW,
        NOW + timedelta(days=1),
        as_of=NOW,
        user_id=1,
        channel_id=10,
        kind="text",
        limit=1,
        after=first.next_cursor,
    )
    bonus = await history.events(
        NOW, NOW + timedelta(days=1), as_of=NOW, user_id=1, channel_id=10, kind="text", bonus_only=True
    )
    # Then
    assert first.next_cursor is not None and second.next_cursor is None
    assert first.events[0].event_id != second.events[0].event_id
    assert len(bonus.events) == 1 and bonus.events[0].bonus_shard == 10
    recorded = NOW + timedelta(days=120)
    late = await repo.award_message(MessageAward(6, 1, "text", NOW, recorded, 10, channel_id=10))
    received = await history.events(recorded, recorded + timedelta(days=1), as_of=recorded, time_basis="recorded")
    assert [row.event_id for row in received.events] == [late.event_id]


@pytest.mark.asyncio
async def test_repair_uses_inputs(sessions: async_sessionmaker[AsyncSession]) -> None:
    """イベント回収後も正本入力からcacheを復元し、恒常・原本入力を変えない。"""
    # 非機能要件：90日履歴を残高の無期限正本にしない。
    # Given
    gate = MutationGate()
    repo = LevelingRepository(sessions, gate=gate, coverage_start_at=NOW)
    await CatalogueRepository(sessions, gate).observe_channel(10, "channel", "text", NOW)
    event = await repo.award_message(MessageAward(1, 1, "text", NOW, NOW, 10, channel_id=10))
    period_id = event.accepted_period_ids[0]
    async with sessions() as session:
        user = (await session.scalars(select(PeriodUser).where(PeriodUser.period_id == period_id))).one()
        channel = (await session.scalars(select(PeriodChannel).where(PeriodChannel.period_id == period_id))).one()
        user.text_power = user.total_power = channel.power = 999
        await session.commit()
    await RetentionRepository(sessions, gate).purge(NOW + timedelta(days=100))
    maintenance = MaintenanceRepository(sessions, gate)
    # When
    result = await maintenance.repair_open(period_id, operation_key="repair", actor_id=99, now=NOW)
    # Then
    assert result.users == result.channels == 1
    assert await maintenance.repair_open(period_id, operation_key="repair", actor_id=99, now=NOW) == result
    async with sessions() as session:
        user = (await session.scalars(select(PeriodUser).where(PeriodUser.period_id == period_id))).one()
        channel = (await session.scalars(select(PeriodChannel).where(PeriodChannel.period_id == period_id))).one()
        assert user.text_power == user.total_power == channel.power == 10
        assert user.unallocated_text == 0
    account = await repo.get_account(1)
    assert account is not None and account.text_shard == 10
    audit = await HistoryRepository(sessions).operation("repair")
    assert audit is not None and audit.kind == "cache_repair"
