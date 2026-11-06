from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import Claim, OutboxJob, PeriodRow, RankingRevision, RankingRow, VoicePending
from app.database.repositories.leveling_v2 import LevelingRepository, MessageAward, MutationGate
from app.database.repositories.leveling_v2.closing import close_period, find_closed
from app.database.repositories.leveling_v2.messages import apply_message, find_message
from app.database.repositories.leveling_v2.snapshots import verify_revision
from app.database.repositories.leveling_v2.transaction import Transactions
from app.features.leveling.domain.periods import PeriodKind, period_at

NOW = datetime(2026, 10, 15, tzinfo=UTC)


@pytest.mark.asyncio
@pytest.mark.parametrize("close_first", [False, True])
async def test_lock_order_outcome(sessions: async_sessionmaker[AsyncSession], close_first: bool) -> None:
    """加算先行と締め先行のどちらでも日・週・月の受理結果と公開版が一致する。"""
    # 非機能要件：D04/D05の両ロック順を固定し、確定した日だけが後続加算を拒否する。
    # Given
    day = period_at(NOW, PeriodKind.DAY)
    request = MessageAward(1, 1, "text", NOW, day.end, 10)
    started = asyncio.Event()

    async def second():
        started.set()
        transactions = Transactions(sessions)
        if close_first:
            return await transactions.run(
                lambda session: apply_message(session, request, NOW),
                lambda session: find_message(session, 1, day.end),
            )
        return await transactions.run(
            lambda session: close_period(session, day, day.end, NOW),
            lambda session: find_closed(session, day),
        )

    # When
    async with sessions() as first:
        if close_first:
            await close_period(first, day, day.end, NOW)
        else:
            await apply_message(first, request, NOW)
        pending = asyncio.create_task(second())
        await asyncio.wait_for(started.wait(), timeout=5)
        await first.commit()
    await asyncio.wait_for(pending, timeout=10)

    # Then
    async with sessions() as session:
        result = await find_message(session, 1, day.end)
        assert result.found and result.value is not None
        rows = list(await session.scalars(select(PeriodRow)))
        daily = next(row for row in rows if row.kind == "day")
        assert len(result.value.accepted_period_ids) == (2 if close_first else 3)
        assert result.value.rejected_period_ids == ((daily.period_id,) if close_first else ())
        await verify_revision(session, daily.period_id, 1)
        scores = list(await session.scalars(select(RankingRow.score).where(RankingRow.period_id == daily.period_id)))
        assert scores == ([] if close_first else [10, 10])


@pytest.mark.asyncio
async def test_close_failure(sessions: async_sessionmaker[AsyncSession]) -> None:
    """月末の最後のジョブ書込み後に失敗しても受取・公開・ジョブは全て元に戻る。"""
    # 非機能要件：D07の最終commit前失敗は旧pendingを保ち、再実行で一度だけ公開する。
    # Given
    month = period_at(NOW, PeriodKind.MONTH)
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    await repo.award_message(MessageAward(1, 1, "text", NOW, NOW, 10))
    async with sessions() as session:
        row = (await session.scalars(select(PeriodRow).where(PeriodRow.kind == "month"))).one()
        period_id = row.period_id
        session.add(VoicePending(user_id=1, month_period_id=period_id, origin="native", voice_shard=30))
        await session.commit()

    def inject(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO leveling_outbox "):
            raise RuntimeError("injected close failure")

    async def action(session: AsyncSession):
        connection = (await session.connection()).sync_connection
        event.listen(connection, "after_cursor_execute", inject)
        try:
            return await close_period(session, month, month.end, NOW)
        finally:
            event.remove(connection, "after_cursor_execute", inject)

    # When
    with pytest.raises(RuntimeError, match="injected close failure"):
        await Transactions(sessions).run(action, lambda session: find_closed(session, month))

    # Then
    async with sessions() as session:
        for model in (Claim, RankingRevision, OutboxJob):
            assert await session.scalar(select(func.count()).select_from(model)) == 0
        row = await session.get(PeriodRow, period_id)
        balance = await session.get(VoicePending, (1, period_id, "native"))
        assert row is not None and row.status == "OPEN"
        assert balance is not None and balance.voice_shard == 30
    revision = await repo.close_period(month, month.end)
    assert await repo.close_period(month, month.end) == revision
    account = await repo.get_account(1)
    assert account is not None and account.growth.total == 40
