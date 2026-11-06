"""承認された永久報酬判断の保存と同期ジョブ予約。Discord操作は行わない。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.leveling_v2 import CorrectionRoleChoice, PermanentAward, RoleDesire
from app.features.leveling.domain.numbers import boolean, identifier

from .outbox import enqueue
from .storage import ensure
from .transaction import OperationConflict


@dataclass(frozen=True)
class RoleDecision:
    user_id: int
    role_id: int
    old_qualified: bool
    new_qualified: bool
    old_desired: bool
    new_desired: bool
    decision: str

    def __post_init__(self) -> None:
        identifier(self.user_id)
        identifier(self.role_id)
        for value in (self.old_qualified, self.new_qualified, self.old_desired, self.new_desired):
            boolean(value)
        if self.decision not in ("keep", "revoke"):
            raise ValueError("永久報酬の判断が不正です")
        if self.decision == "keep" and self.new_desired != self.old_desired:
            raise ValueError("維持では希望状態を変更できません")
        if self.decision == "revoke" and (self.new_desired or self.new_qualified):
            raise ValueError("資格が残る永久報酬は剥奪できません")


async def apply_role_decisions(
    session: AsyncSession,
    choices: tuple[RoleDecision, ...],
    *,
    correction_id: int,
    operation_key: str,
    period_id: int,
    revision: int,
    now: datetime,
) -> None:
    # 永久獲得記録を先に全件確認・更新し、その後role_desireをPK順で取得する。
    for choice in sorted(choices, key=lambda item: item.user_id):
        award = await session.get(PermanentAward, (choice.user_id, "three_month_top1"), with_for_update=True)
        if award is None or award.desired_granted != choice.old_desired:
            raise OperationConflict("承認後に永久報酬の希望状態が変更されています")
        award.desired_granted = choice.new_desired
        award.decision_version += 1
        award.last_correction_id = correction_id
        session.add(
            CorrectionRoleChoice(
                correction_id=correction_id,
                user_id=choice.user_id,
                role_id=choice.role_id,
                old_qualified=choice.old_qualified,
                new_qualified=choice.new_qualified,
                decision=choice.decision,
                old_desired=choice.old_desired,
                new_desired=choice.new_desired,
            )
        )
    await session.flush()
    jobs: list[tuple[RoleDecision, int]] = []
    for choice in sorted(choices, key=lambda item: (item.user_id, item.role_id)):
        await ensure(
            session,
            RoleDesire,
            {"user_id": choice.user_id, "role_id": choice.role_id, "desired": choice.old_desired, "generation": 0},
            "user_id",
        )
        row = (
            await session.scalars(
                select(RoleDesire)
                .where(
                    RoleDesire.user_id == choice.user_id,
                    RoleDesire.role_id == choice.role_id,
                )
                .with_for_update()
            )
        ).one()
        if row.desired != choice.old_desired:
            raise OperationConflict("承認後にロール同期の希望状態が変更されています")
        row.desired = choice.new_desired
        row.generation += 1
        row.source_month = period_id
        row.source_revision = revision
        jobs.append((choice, row.generation))
    for choice, generation in jobs:
        await enqueue(
            session,
            dedupe_key=f"role:{choice.user_id}:{choice.role_id}:{generation}",
            job_type="role_sync",
            payload={
                "correction_id": correction_id,
                "user_id": choice.user_id,
                "role_id": choice.role_id,
                "generation": generation,
                "desired": choice.new_desired,
            },
            now=now,
            audit_operation_key=operation_key,
        )
