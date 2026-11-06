"""期間確定のDB最終段階。Discord・VC計測drainは呼び出さない。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.leveling_v2 import Account, PeriodRow, VoicePending, VoiceSegmentRow, VoiceState
from app.features.leveling.domain.periods import Period, aware

from .claims import ClaimRequest, claim_locked
from .dto import RevisionResult
from .outbox import enqueue
from .qualifications import lock_publication_periods, preserve_awards, rebuild_qualifications
from .snapshots import open_inputs, save_revision, verify_revision
from .storage import lock_accounts, lock_pending, lock_states
from .transaction import Resolution


async def find_closed(session: AsyncSession, period: Period) -> Resolution[RevisionResult]:
    row = (
        await session.scalars(
            select(PeriodRow).where(
                PeriodRow.kind == period.kind.value,
                PeriodRow.start_at == period.start,
            )
        )
    ).one_or_none()
    if row is None or row.status != "FINALIZED":
        return Resolution(False)
    # 初回締めの結果を返す。後続訂正によるpointer変更と混同しない。
    return Resolution(True, await verify_revision(session, row.period_id, 1))


async def close_period(
    session: AsyncSession,
    period: Period,
    now: datetime,
    coverage: datetime,
) -> RevisionResult:
    aware(now)
    if not period.has_ended(now):
        raise ValueError("期間終了前に確定できません")
    row, months = await lock_publication_periods(session, period, coverage)
    if row.status == "FINALIZED":
        return await verify_revision(session, row.period_id, 1)
    # 保存済みの既知区間を捨てて締めない。P3/P4のdrainはロック取得前に別txで完了させる。
    unconsumed = await session.scalar(
        select(VoiceSegmentRow.user_id)
        .where(
            VoiceSegmentRow.start_at < row.end_at,
            VoiceSegmentRow.end_at > row.start_at,
        )
        .limit(1)
    )
    if unconsumed is not None:
        raise ValueError("対象期間の未精算VC区間が残っています")
    accounts: list[Account] = []
    states: dict[int, VoiceState] = {}
    pending: list[VoicePending] = []
    if row.kind == "month":
        users = tuple(await session.scalars(select(Account.user_id).order_by(Account.user_id)))
        accounts = await lock_accounts(session, users)
        states = {state.user_id: state for state in await lock_states(session, users)}
        pending = await lock_pending(session, users)
    result = await save_revision(session, row.period_id, 1, await open_inputs(session, row.period_id), now)
    await verify_revision(session, row.period_id, 1)
    row.status = "FINALIZED"
    row.current_revision = 1
    row.finalized_at = now
    awards = await rebuild_qualifications(session, months, coverage)
    # 集計入力まで処理した後、永久claim→報酬→outboxの順に確定する。
    claim_users = {item.user_id for item in pending if item.month_period_id == row.period_id}
    for account in accounts:
        if account.user_id in claim_users:
            await claim_locked(
                session,
                ClaimRequest(
                    f"month_close:{row.period_id}:{account.user_id}",
                    account.user_id,
                    "month_close",
                    now,
                    row.period_id,
                ),
                account,
                states.get(account.user_id),
                pending,
            )
    await preserve_awards(session, awards, now)
    await enqueue(
        session,
        dedupe_key=f"period_finalized:{row.period_id}:1",
        job_type="period_finalized",
        payload={"period_id": row.period_id, "revision": 1},
        now=now,
    )
    await session.flush()
    return result
