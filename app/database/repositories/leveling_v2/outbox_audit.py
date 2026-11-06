"""Outbox詳細の回収前に、結果を永久監査へ同一txで転記する。"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.leveling_v2 import Correction, CorrectionRoleChoice, Operation, OutboxJob
from app.features.leveling.domain.numbers import identifier


async def lock_audit(session: AsyncSession, job_id: int) -> tuple[Operation | None, CorrectionRoleChoice | None]:
    # outbox自身の排他取得前に、永久operation/choiceを先に取得する。
    job = await session.get(OutboxJob, job_id)
    if job is None or job.audit_operation_key is None:
        return None, None
    operation = (
        await session.scalars(
            select(Operation).where(Operation.operation_key == job.audit_operation_key).with_for_update()
        )
    ).one()
    choice = None
    if job.type == "role_sync":
        keys = tuple(job.payload.get(key) for key in ("correction_id", "user_id", "role_id"))
        if any(type(value) is not int for value in keys):
            raise ValueError("ロール結果の永久監査参照が不正です")
        correction_id, user_id, role_id = (identifier(int(str(value))) for value in keys)
        correction = await session.get(Correction, correction_id)
        if correction is None or operation.operation_key != f"correction:{correction.request_key}":
            raise ValueError("訂正と操作台帳の参照が一致しません")
        choice = (
            await session.scalars(
                select(CorrectionRoleChoice)
                .where(
                    CorrectionRoleChoice.correction_id == correction_id,
                    CorrectionRoleChoice.user_id == user_id,
                    CorrectionRoleChoice.role_id == role_id,
                )
                .with_for_update()
            )
        ).one_or_none()
        if choice is None:
            raise ValueError("承認済みロール判断が存在しません")
    return operation, choice


def completed_result(operation: Operation | None, job: OutboxJob) -> object:
    if operation is None:
        return None
    results = operation.after_values.get("outbox_results", {})
    if not isinstance(results, dict):
        raise ValueError("永久監査の完了結果が不正です")
    return results.get(job.dedupe_key)


def record_completion(
    operation: Operation | None,
    choice: CorrectionRoleChoice | None,
    job: OutboxJob,
    now: datetime,
    result: str,
) -> None:
    if operation is None:
        return
    after = deepcopy(operation.after_values)
    results = after.setdefault("outbox_results", {})
    if not isinstance(results, dict):
        raise ValueError("永久監査の完了結果が不正です")
    results[job.dedupe_key] = {
        "job_id": job.job_id,
        "lease_token": job.lease_token,
        "result": result,
        "completed_at": now.isoformat(),
        "type": job.type,
    }
    operation.after_values = after
    if choice is not None:
        choice.execution_result = result
        choice.completed_at = now


async def completion_is_preserved(session: AsyncSession, job: OutboxJob) -> bool:
    if job.audit_operation_key is None:
        return True
    operation = await session.get(Operation, job.audit_operation_key)
    result = completed_result(operation, job)
    return isinstance(result, dict) and result.get("job_id") == job.job_id and bool(result.get("completed_at"))
