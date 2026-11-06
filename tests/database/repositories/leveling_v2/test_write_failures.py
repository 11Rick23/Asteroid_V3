from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import Account, Event, MessageReceipt, PeriodRow, PeriodUser
from app.database.repositories.leveling_v2 import LevelingRepository, MessageAward, MutationGate
from app.database.repositories.leveling_v2.messages import apply_message, find_message
from app.database.repositories.leveling_v2.transaction import Transactions

NOW = datetime(2026, 10, 15, tzinfo=UTC)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("statement_prefix", "occurrence"),
    [
        ("UPDATE leveling_accounts", 1),
        ("UPDATE leveling_period_users", 2),
        ("INSERT INTO leveling_events ", 1),
        ("INSERT INTO leveling_message_receipts ", 1),
    ],
)
async def test_write_failure(
    sessions: async_sessionmaker[AsyncSession], statement_prefix: str, occurrence: int
) -> None:
    """恒常・期間途中・イベント・receipt書込み後の障害は全rollbackされ、再実行できる。"""
    # 非機能要件：D03の各書込み境界で失敗しても部分計上や再送拒否を残さない。
    # Given
    request = MessageAward(1, 1, "text", NOW, NOW, 10)
    seen = 0

    def inject(connection, cursor, statement, parameters, context, executemany):
        nonlocal seen
        if statement.startswith(statement_prefix):
            seen += 1
            if seen == occurrence:
                raise RuntimeError("injected write failure")

    async def action(session: AsyncSession):
        connection = (await session.connection()).sync_connection
        event.listen(connection, "after_cursor_execute", inject)
        try:
            return await apply_message(session, request, NOW)
        finally:
            event.remove(connection, "after_cursor_execute", inject)

    # When
    with pytest.raises(RuntimeError, match="injected write failure"):
        await Transactions(sessions).run(action, lambda session: find_message(session, 1, NOW))

    # Then
    assert seen == occurrence
    async with sessions() as session:
        for model in (Account, PeriodRow, PeriodUser, Event, MessageReceipt):
            assert await session.scalar(select(func.count()).select_from(model)) == 0
    repo = LevelingRepository(sessions, gate=MutationGate(), coverage_start_at=NOW)
    first = await repo.award_message(request)
    assert await repo.award_message(request) == first
    account = await repo.get_account(1)
    assert account is not None and account.text_shard == 10
