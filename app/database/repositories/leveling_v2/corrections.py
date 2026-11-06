"""承認済み入力集合のrevision公開基盤。プレビューUI・Discord権限判定はP4/P5。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.leveling_v2 import (
    Account,
    Correction,
    CorrectionChange,
    MonthlyQualification,
    Operation,
    PeriodRow,
)
from app.features.leveling.domain.numbers import identifier
from app.features.leveling.domain.periods import Period, PeriodKind, aware

from .dto import RevisionResult
from .outbox import enqueue
from .qualifications import lock_publication_periods, preserve_awards, rebuild_qualifications
from .role_decisions import RoleDecision, apply_role_decisions
from .snapshots import SnapshotInputs, revision_inputs, save_revision, snapshot_content, verify_revision
from .storage import lock_accounts
from .transaction import OperationConflict, Resolution


@dataclass(frozen=True)
class SnapshotCorrection:
    request_key: str
    period_id: int
    expected_revision: int
    actor_id: int
    reason: str
    requested_at: datetime
    approved_at: datetime
    preview_hash: str
    inputs: SnapshotInputs
    reannounce: bool = False
    role_decisions: tuple[RoleDecision, ...] = ()

    def __post_init__(self) -> None:
        for value in (self.period_id, self.expected_revision, self.actor_id):
            identifier(value)
        if not self.request_key or len(self.request_key) > 170 or not self.reason.strip():
            raise ValueError("訂正キーと理由を指定してください")
        aware(self.requested_at)
        aware(self.approved_at)
        if not self.requested_at <= self.approved_at <= self.requested_at + timedelta(minutes=15):
            raise ValueError("訂正プレビューの承認期限が不正です")
        if type(self.reannounce) is not bool:
            raise ValueError("再発表の選択が不正です")
        # 呼出し側による承認後の辞書変更を切り離す。
        object.__setattr__(self, "inputs", SnapshotInputs(dict(self.inputs.users), dict(self.inputs.channels)))
        if len({choice.user_id for choice in self.role_decisions}) != len(self.role_decisions):
            raise ValueError("同じユーザーの永久報酬判断が重複しています")

    def digest(self) -> str:
        _, _, checksum = snapshot_content(self.inputs)
        payload = [
            self.request_key,
            str(self.period_id),
            str(self.expected_revision),
            str(self.actor_id),
            self.reason,
            self.requested_at.isoformat(),
            self.reannounce,
            checksum,
            [asdict(choice) for choice in sorted(self.role_decisions, key=lambda item: item.user_id)],
        ]
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

    @property
    def operation_key(self) -> str:
        return f"correction:{self.request_key}"


async def find_correction(session: AsyncSession, request: SnapshotCorrection) -> Resolution[RevisionResult]:
    operation = await session.get(Operation, request.operation_key)
    if operation is None:
        return Resolution(False)
    if operation.kind != "ranking_correction" or operation.request_hash != request.digest():
        raise ValueError("訂正キーが別の要求に使用されています")
    revision = operation.after_values.get("revision")
    if type(revision) is not int:
        raise ValueError("訂正台帳のrevisionが不正です")
    return Resolution(True, await verify_revision(session, request.period_id, revision))


async def correct_snapshot(session: AsyncSession, request: SnapshotCorrection) -> RevisionResult:
    if request.preview_hash != request.digest():
        raise ValueError("承認内容とpreview hashが一致しません")
    existing = await find_correction(session, request)
    if existing.found and existing.value is not None:
        return existing.value
    initial = await session.get(PeriodRow, request.period_id)
    if initial is None:
        raise ValueError("訂正対象期間が存在しません")
    period = Period(PeriodKind(initial.kind), initial.start_at, initial.end_at)
    row, months = await lock_publication_periods(session, period, initial.coverage_start_at)
    if row.status != "FINALIZED" or row.current_revision != request.expected_revision:
        raise OperationConflict("承認後に対象revisionが変更されています")
    if request.role_decisions and row.kind != "month":
        raise ValueError("永久報酬判断は月間訂正で指定してください")
    old_qualified = (
        set(
            await session.scalars(
                select(MonthlyQualification.user_id).where(
                    MonthlyQualification.consecutive_top1 >= 3,
                )
            )
        )
        if request.role_decisions
        else set()
    )
    previous = await verify_revision(session, row.period_id, row.current_revision)
    before = await revision_inputs(session, row.period_id, row.current_revision)
    users = tuple(sorted(set(request.inputs.users) | {user for _, _, user in request.inputs.channels}))
    if months:
        users = tuple(sorted(set(users) | set(await session.scalars(select(Account.user_id)))))
    await lock_accounts(session, users)
    correction = Correction(
        request_key=request.request_key,
        actor_id=request.actor_id,
        reason=request.reason,
        requested_at=request.requested_at,
        approved_at=request.approved_at,
        preview_hash=request.preview_hash,
        reannounce=request.reannounce,
        status="completed",
    )
    session.add(correction)
    await session.flush()
    result = await save_revision(
        session,
        row.period_id,
        row.current_revision + 1,
        request.inputs,
        request.approved_at,
        correction_id=correction.correction_id,
    )
    old_rows = {tuple(r[:4]): (r[4], r[5]) for r in snapshot_content(before)[0]}
    new_rows = {tuple(r[:4]): (r[4], r[5]) for r in snapshot_content(request.inputs)[0]}
    changes = sorted(old_rows.keys() | new_rows.keys())
    seq = 0
    for key in changes:
        old_score, old_rank = old_rows.get(key, (0, None))
        new_score, new_rank = new_rows.get(key, (0, None))
        if (old_score, old_rank) == (new_score, new_rank):
            continue
        seq += 1
        scope, metric, channel, subject = key
        session.add(
            CorrectionChange(
                correction_id=correction.correction_id,
                change_seq=seq,
                period_id=row.period_id,
                old_revision=row.current_revision,
                new_revision=result.revision,
                scope=scope,
                metric=metric,
                channel_key=channel,
                subject_id=subject,
                old_score=old_score,
                new_score=new_score,
                old_rank=old_rank,
                new_rank=new_rank,
            )
        )
    session.add(
        Operation(
            operation_key=request.operation_key,
            kind="ranking_correction",
            actor_id=request.actor_id,
            request_hash=request.digest(),
            status="completed",
            created_at=request.requested_at,
            completed_at=request.approved_at,
            before_values={
                "period_id": row.period_id,
                "revision": row.current_revision,
                "checksum": previous.checksum,
            },
            after_values={"period_id": row.period_id, "revision": result.revision, "checksum": result.checksum},
        )
    )
    await session.flush()
    await verify_revision(session, row.period_id, result.revision)
    row.current_revision = result.revision
    awards = await rebuild_qualifications(session, months, row.coverage_start_at)
    eligible = {user for user, _ in awards}
    for choice in request.role_decisions:
        if choice.old_qualified != (choice.user_id in old_qualified) or choice.new_qualified != (
            choice.user_id in eligible
        ):
            raise ValueError("承認したロール資格と再計算結果が一致しません")
    await preserve_awards(session, awards, request.approved_at)
    await apply_role_decisions(
        session,
        request.role_decisions,
        correction_id=correction.correction_id,
        operation_key=request.operation_key,
        period_id=row.period_id,
        revision=result.revision,
        now=request.approved_at,
    )
    if request.reannounce:
        await enqueue(
            session,
            dedupe_key=f"period_corrected:{row.period_id}:{result.revision}",
            job_type="period_corrected",
            payload={"period_id": row.period_id, "revision": result.revision},
            now=request.approved_at,
            audit_operation_key=request.operation_key,
        )
    await session.flush()
    return result
