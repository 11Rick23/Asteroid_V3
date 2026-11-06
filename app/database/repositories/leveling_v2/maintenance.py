"""OPEN正本から派生cacheを修復する。イベントを再生して残高を作らない。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import PeriodChannel, PeriodChannelUser, PeriodRow, PeriodUser
from app.features.leveling.domain.numbers import identifier
from app.features.leveling.domain.periods import aware

from .audit import find_operation, record_operation, request_digest
from .locks import MutationGate
from .snapshots import open_inputs
from .storage import ensure, lock_accounts
from .transaction import Resolution, Transactions


@dataclass(frozen=True)
class RepairResult:
    period_id: int
    users: int
    channels: int


class MaintenanceRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], gate: MutationGate) -> None:
        self.sessions = sessions
        self.gate = gate
        self.transactions = Transactions(sessions)

    async def repair_open(
        self,
        period_id: int,
        *,
        operation_key: str,
        actor_id: int,
        now: datetime,
    ) -> RepairResult:
        identifier(period_id)
        identifier(actor_id)
        aware(now)
        digest = request_digest({"period_id": period_id})

        async def resolve(session: AsyncSession) -> Resolution[RepairResult]:
            found = await find_operation(session, operation_key, "cache_repair", actor_id, digest)
            if not found.found or found.value is None:
                return Resolution(False)
            return Resolution(
                True, RepairResult(period_id, int(str(found.value["users"])), int(str(found.value["channels"])))
            )

        async def action(session: AsyncSession) -> RepairResult:
            existing = await resolve(session)
            if existing.found and existing.value is not None:
                return existing.value
            period = (
                await session.scalars(select(PeriodRow).where(PeriodRow.period_id == period_id).with_for_update())
            ).one_or_none()
            if period is None or period.status != "OPEN":
                raise ValueError("OPEN期間だけをcache修復できます")
            users = set(await session.scalars(select(PeriodUser.user_id).where(PeriodUser.period_id == period_id)))
            users.update(
                await session.scalars(
                    select(PeriodChannelUser.user_id).where(PeriodChannelUser.period_id == period_id)
                )
            )
            await lock_accounts(session, tuple(users))
            # periodロックで入力writerを止めた上で読み、table階層に沿ってcacheをロックする。
            inputs = await open_inputs(session, period_id, lock=False)
            scores = inputs.scores()
            for user in sorted(users):
                await ensure(session, PeriodUser, {"period_id": period_id, "user_id": user}, "user_id")
                row = (
                    await session.scalars(
                        select(PeriodUser)
                        .where(
                            PeriodUser.period_id == period_id,
                            PeriodUser.user_id == user,
                        )
                        .with_for_update()
                    )
                ).one()
                row.text_power = scores.get(("user", "text", 0), {}).get(user, 0)
                row.voice_power = scores.get(("user", "voice", 0), {}).get(user, 0)
                row.total_power = scores.get(("user", "total", 0), {}).get(user, 0)
            old_channels = list(
                await session.scalars(select(PeriodChannel).where(PeriodChannel.period_id == period_id))
            )
            channel_keys = {(row.channel_id, row.kind) for row in old_channels}
            channel_keys.update((channel, kind) for channel, kind, _ in inputs.channels)
            for channel, kind in sorted(channel_keys):
                await ensure(
                    session, PeriodChannel, {"period_id": period_id, "channel_id": channel, "kind": kind}, "channel_id"
                )
                row = (
                    await session.scalars(
                        select(PeriodChannel)
                        .where(
                            PeriodChannel.period_id == period_id,
                            PeriodChannel.channel_id == channel,
                            PeriodChannel.kind == kind,
                        )
                        .with_for_update()
                    )
                ).one()
                row.power = scores.get(("channel", kind, 0), {}).get(channel, 0)
            result = RepairResult(period_id, len(users), len(channel_keys))
            await record_operation(
                session,
                key=operation_key,
                kind="cache_repair",
                actor_id=actor_id,
                digest=digest,
                before={},
                after={"period_id": period_id, "users": result.users, "channels": result.channels},
                now=now,
            )
            return result

        async with self.gate.exclusive():
            return await self.transactions.run(action, resolve)
