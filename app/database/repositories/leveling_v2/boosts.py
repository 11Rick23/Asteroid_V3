"""予約履歴は無期限保存し、取消時刻で有効区間を閉じる。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import Boost as BoostRow
from app.features.leveling.domain.boosts import Boost
from app.features.leveling.domain.numbers import identifier, integer
from app.features.leveling.domain.periods import aware

from .audit import find_operation, record_operation, request_digest
from .locks import MutationGate
from .transaction import OperationConflict, Resolution, Transactions


@dataclass(frozen=True)
class BoostData:
    boost: Boost
    name: str
    version: int


def boost_data(row: BoostRow) -> BoostData:
    return BoostData(
        Boost(row.boost_id, row.role_id, row.rate_percent, row.starts_at, row.ends_at, row.cancelled_at),
        row.name,
        row.version,
    )


def values(data: BoostData) -> dict[str, object]:
    boost = data.boost
    return {
        "boost_id": boost.boost_id,
        "role_id": boost.role_id,
        "rate_percent": str(boost.rate_percent),
        "start": boost.start.isoformat(),
        "end": None if boost.end is None else boost.end.isoformat(),
        "cancelled_at": None if boost.cancelled_at is None else boost.cancelled_at.isoformat(),
        "name": data.name,
        "version": data.version,
    }


def from_values(data: dict[str, object]) -> BoostData:
    def number(key: str) -> int:
        value = data[key]
        if type(value) is not int:
            raise ValueError("ブースト監査の数値型が不正です")
        return value

    return BoostData(
        Boost(
            number("boost_id"),
            number("role_id"),
            int(str(data["rate_percent"])),
            datetime.fromisoformat(str(data["start"])),
            None if data["end"] is None else datetime.fromisoformat(str(data["end"])),
            None if data["cancelled_at"] is None else datetime.fromisoformat(str(data["cancelled_at"])),
        ),
        str(data["name"]),
        number("version"),
    )


class BoostRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], gate: MutationGate) -> None:
        self.sessions = sessions
        self.gate = gate
        self.transactions = Transactions(sessions)

    async def list(self, *, role_id: int | None = None) -> tuple[BoostData, ...]:
        if role_id is not None:
            identifier(role_id)
        async with self.sessions() as session:
            query = select(BoostRow).order_by(BoostRow.boost_id)
            if role_id is not None:
                query = query.where(BoostRow.role_id == role_id)
            return tuple(boost_data(row) for row in await session.scalars(query))

    async def create(
        self,
        *,
        operation_key: str,
        actor_id: int,
        name: str,
        role_id: int,
        rate_percent: int,
        starts_at: datetime,
        ends_at: datetime | None,
        now: datetime,
    ) -> BoostData:
        # IDはDB採番。その他の数量・区間制約はP1値オブジェクトで検査する。
        candidate = Boost(1, role_id, rate_percent, starts_at, ends_at)
        identifier(actor_id)
        aware(now)
        if not name or len(name) > 100:
            raise ValueError("ブースト名が不正です")
        digest = request_digest(
            {
                "name": name,
                "role_id": role_id,
                "rate_percent": str(rate_percent),
                "start": candidate.start.isoformat(),
                "end": None if candidate.end is None else candidate.end.isoformat(),
            }
        )

        async def resolve(session: AsyncSession) -> Resolution[BoostData]:
            found = await find_operation(session, operation_key, "boost_create", actor_id, digest)
            return Resolution(found.found, None if found.value is None else from_values(found.value))

        async def action(session: AsyncSession) -> BoostData:
            existing = await resolve(session)
            if existing.found and existing.value is not None:
                return existing.value
            row = BoostRow(
                role_id=role_id, name=name, rate_percent=rate_percent, starts_at=candidate.start, ends_at=candidate.end
            )
            session.add(row)
            await session.flush()
            result = boost_data(row)
            await record_operation(
                session,
                key=operation_key,
                kind="boost_create",
                actor_id=actor_id,
                digest=digest,
                before={},
                after=values(result),
                now=now,
            )
            return result

        async with self.gate.exclusive():
            return await self.transactions.run(action, resolve)

    async def cancel(
        self,
        boost_id: int,
        expected_version: int,
        *,
        operation_key: str,
        actor_id: int,
        now: datetime,
    ) -> BoostData:
        identifier(boost_id)
        identifier(actor_id)
        integer(expected_version, maximum=2**64 - 2)
        aware(now)
        digest = request_digest({"boost_id": boost_id, "version": expected_version, "cancelled_at": now.isoformat()})

        async def resolve(session: AsyncSession) -> Resolution[BoostData]:
            found = await find_operation(session, operation_key, "boost_cancel", actor_id, digest)
            return Resolution(found.found, None if found.value is None else from_values(found.value))

        async def action(session: AsyncSession) -> BoostData:
            existing = await resolve(session)
            if existing.found and existing.value is not None:
                return existing.value
            row = (
                await session.scalars(select(BoostRow).where(BoostRow.boost_id == boost_id).with_for_update())
            ).one_or_none()
            if row is None:
                raise ValueError("ブースト予約が存在しません")
            if row.version != expected_version or row.cancelled_at is not None:
                raise OperationConflict("予約のversionまたは取消状態が変わっています")
            before = values(boost_data(row))
            row.cancelled_at = now
            row.version += 1
            result = boost_data(row)
            await record_operation(
                session,
                key=operation_key,
                kind="boost_cancel",
                actor_id=actor_id,
                digest=digest,
                before=before,
                after=values(result),
                now=now,
            )
            return result

        async with self.gate.exclusive():
            return await self.transactions.run(action, resolve)
