"""月間資格cache。連続判定はP1に委譲し、永久獲得履歴と分離する。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.leveling_v2 import MonthlyQualification, PeriodRow, PermanentAward, RankingRow
from app.features.leveling.domain.periods import Period, PeriodKind, period_at
from app.features.leveling.domain.rankings import MonthlyResult, top1_qualification

from .storage import lock_periods


async def lock_publication_periods(
    session: AsyncSession,
    target: Period,
    coverage: datetime,
) -> tuple[PeriodRow, list[PeriodRow]]:
    """排他gate下で必要な月集合を最初に列挙し、全periodを固定順で取得する。"""
    planned = [target]
    if target.kind == PeriodKind.MONTH:
        planned.extend(
            Period(PeriodKind.MONTH, row.start_at, row.end_at)
            for row in await session.scalars(
                select(PeriodRow).where(PeriodRow.kind == "month"),
            )
        )
    rows = await lock_periods(session, tuple(planned), coverage)
    selected = next(row for row in rows if row.kind == target.kind.value and row.start_at == target.start)
    return selected, rows if target.kind == PeriodKind.MONTH else []


async def rebuild_qualifications(
    session: AsyncSession,
    months: list[PeriodRow],
    coverage: datetime,
) -> tuple[tuple[int, int], ...]:
    """ロック済み全月の公開版から再計算。通常変動で永久報酬の希望を剥奪しない。"""
    start = period_at(coverage, PeriodKind.MONTH).start
    finalized = [month for month in months if month.status == "FINALIZED" and month.start_at >= start]
    if not finalized:
        return ()
    finalized.sort(key=lambda row: row.start_at)
    by_start = {row.start_at: row for row in finalized}
    results: dict[int, list[MonthlyResult]] = {}
    ranks: dict[tuple[int, int], int] = {}
    for month in sorted(finalized, key=lambda row: row.period_id):
        # current readで、periodロックを待った間の公開結果も取り込む。
        rows = await session.scalars(
            select(RankingRow)
            .where(
                RankingRow.period_id == month.period_id,
                RankingRow.revision == month.current_revision,
                RankingRow.scope == "user",
                RankingRow.metric == "total",
                RankingRow.channel_key == 0,
            )
            .order_by(RankingRow.subject_id)
            .with_for_update()
        )
        for row in rows:
            results.setdefault(row.subject_id, []).append(MonthlyResult(month.start_at, row.score, row.rank))
            ranks[(month.period_id, row.subject_id)] = row.rank
    old_rows = list(
        await session.scalars(
            select(MonthlyQualification)
            .where(
                MonthlyQualification.month_period_id.in_([month.period_id for month in finalized]),
            )
            .order_by(MonthlyQualification.month_period_id, MonthlyQualification.user_id)
            .with_for_update()
        )
    )
    existing = {(row.month_period_id, row.user_id): row for row in old_rows}
    users = sorted(set(results) | {row.user_id for row in old_rows})
    for month in sorted(finalized, key=lambda row: row.period_id):
        for user in users:
            rank = ranks.get((month.period_id, user))
            qualification = top1_qualification(results.get(user, []), start, month.start_at)
            row = existing.get((month.period_id, user))
            if row is None:
                row = MonthlyQualification(month_period_id=month.period_id, user_id=user)
                session.add(row)
            row.ranking_revision = month.current_revision
            row.is_top1 = rank == 1
            row.is_top10 = rank is not None and rank <= 10
            row.consecutive_top1 = qualification.consecutive
    await session.flush()
    awards: list[tuple[int, int]] = []
    for user in users:
        earned = top1_qualification(results.get(user, []), start, finalized[-1].start_at)
        if earned.first_earned_month is None:
            continue
        awards.append((user, by_start[earned.first_earned_month].period_id))
    return tuple(awards)


async def preserve_awards(session: AsyncSession, awards: tuple[tuple[int, int], ...], now: datetime) -> None:
    """claim/operationの確定後に永久報酬の初回獲得だけを追記する。"""
    for user, month_id in awards:
        row = await session.get(PermanentAward, (user, "three_month_top1"), with_for_update=True)
        if row is None:
            session.add(
                PermanentAward(
                    user_id=user,
                    award_type="three_month_top1",
                    first_earned_month=month_id,
                    earned_at=now,
                    desired_granted=True,
                    decision_version=1,
                )
            )
    await session.flush()
