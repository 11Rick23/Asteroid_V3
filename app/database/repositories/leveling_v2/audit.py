"""永久operation台帳の内部API。数量変更と同じtxから呼び、独自commitしない。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.leveling_v2 import Operation
from app.features.leveling.domain.numbers import identifier
from app.features.leveling.domain.periods import aware

from .transaction import Resolution


def request_digest(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


async def find_operation(
    session: AsyncSession,
    key: str,
    kind: str,
    actor_id: int,
    digest: str,
) -> Resolution[dict[str, object]]:
    row = await session.get(Operation, key)
    if row is None:
        return Resolution(False)
    if row.kind != kind or row.actor_id != actor_id or row.request_hash != digest:
        raise ValueError("操作キーが別の要求に使用されています")
    if row.status != "completed":
        return Resolution(False)
    return Resolution(True, dict(row.after_values))


async def record_operation(
    session: AsyncSession,
    *,
    key: str,
    kind: str,
    actor_id: int,
    digest: str,
    before: dict[str, object],
    after: dict[str, object],
    now: datetime,
) -> None:
    identifier(actor_id)
    aware(now)
    if not key or len(key) > 191 or not kind or len(kind) > 32 or len(digest) != 64:
        raise ValueError("監査識別子が不正です")
    session.add(
        Operation(
            operation_key=key,
            kind=kind,
            actor_id=actor_id,
            request_hash=digest,
            status="completed",
            before_values=before,
            after_values=after,
            created_at=now,
            completed_at=now,
        )
    )
    await session.flush()
