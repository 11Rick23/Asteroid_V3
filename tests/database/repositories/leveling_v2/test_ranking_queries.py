from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.repositories.leveling_v2 import LevelingRepository, MessageAward, MutationGate
from app.database.repositories.leveling_v2.ranking_queries import RankingRepository
from app.features.leveling.domain.periods import PeriodKind, period_at

NOW = datetime(2026, 10, 15, tzinfo=UTC)


@pytest.mark.asyncio
async def test_rank_before_pagination(sessions: async_sessionmaker[AsyncSession]) -> None:
    """0点を除外してRANKを計算し、同率を維持したままDBページングする。"""
    # 機能要件：OPENと確定版で順位・件数・同率内ID順が一致する。
    # Given
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    reader = RankingRepository(sessions)
    scores = (30, 20, 20, 10, 0)
    event = None
    for user, score in enumerate(scores, 1):
        event = await repo.award_message(MessageAward(user, user, "text", NOW, NOW, score))
    assert event is not None
    period_id = event.accepted_period_ids[0]
    # When
    page = await reader.page(period_id, offset=1, limit=2)
    top = await reader.page(period_id, top_rank=2, limit=100)
    # Then
    assert page is not None and page.count == 4 and page.revision == 0
    assert [(row.subject_id, row.rank) for row in page.entries] == [(2, 2), (3, 2)]
    assert top is not None and top.count == 3
    month = period_at(NOW, PeriodKind.MONTH)
    revision = await repo.close_period(month, month.end)
    fixed = await reader.page(revision.period_id, offset=1, limit=2)
    assert fixed is not None and fixed.entries == page.entries and fixed.count == page.count
    assert fixed.revision == 1
