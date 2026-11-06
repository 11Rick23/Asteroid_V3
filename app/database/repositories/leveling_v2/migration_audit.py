"""移行原本の監査保存だけを提供する。旧DB読取・残高移行・schema切替は行わない。"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import MigrationItem, MigrationRun
from app.features.leveling.domain.numbers import identifier
from app.features.leveling.domain.periods import aware

from .audit import request_digest
from .locks import MutationGate
from .storage import ensure
from .transaction import Resolution, Transactions


@dataclass(frozen=True)
class MigrationRunData:
    migration_id: int
    source_digest: str
    target_generation: int
    status: str


@dataclass(frozen=True)
class MigrationItemData:
    source_table: str
    source_key: str
    source_values: dict[str, object]
    target_keys: dict[str, object]
    applied_at: datetime

    def __post_init__(self) -> None:
        if not self.source_table or len(self.source_table) > 64 or not self.source_key or len(self.source_key) > 191:
            raise ValueError("移行原本キーが不正です")
        aware(self.applied_at)
        object.__setattr__(self, "source_values", deepcopy(self.source_values))
        object.__setattr__(self, "target_keys", deepcopy(self.target_keys))
        request_digest(self.source_values)
        request_digest(self.target_keys)


class MigrationAuditRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], gate: MutationGate) -> None:
        self.sessions = sessions
        self.gate = gate
        self.transactions = Transactions(sessions)

    async def prepare(
        self,
        *,
        source_revision: str,
        source_digest: str,
        target_generation: int,
        cutover_at: datetime,
        checksums: dict[str, object],
    ) -> MigrationRunData:
        identifier(target_generation)
        aware(cutover_at)
        if not source_revision or len(source_revision) > 64 or len(source_digest) != 64:
            raise ValueError("移行識別子が不正です")
        if any(character not in "0123456789abcdef" for character in source_digest):
            raise ValueError("原本digestは正規化SHA256文字列で指定してください")
        saved_checksums = deepcopy(checksums)
        request_digest(saved_checksums)

        def result(row: MigrationRun) -> MigrationRunData:
            if (
                row.source_revision != source_revision
                or row.target_generation != target_generation
                or row.cutover_at != cutover_at
                or row.checksums != saved_checksums
            ):
                raise ValueError("同じ原本digestが別の移行要求に使用されています")
            return MigrationRunData(row.migration_id, row.source_digest, row.target_generation, row.status)

        async def resolve(session: AsyncSession) -> Resolution[MigrationRunData]:
            row = await session.scalars(select(MigrationRun).where(MigrationRun.source_digest == source_digest))
            found = row.one_or_none()
            return Resolution(found is not None, None if found is None else result(found))

        async def action(session: AsyncSession) -> MigrationRunData:
            await ensure(
                session,
                MigrationRun,
                {
                    "source_revision": source_revision,
                    "source_digest": source_digest,
                    "target_generation": target_generation,
                    "cutover_at": cutover_at,
                    "status": "prepared",
                    "checksums": saved_checksums,
                },
                "migration_id",
            )
            row = (
                await session.scalars(
                    select(MigrationRun).where(MigrationRun.source_digest == source_digest).with_for_update()
                )
            ).one()
            return result(row)

        async with self.gate.exclusive():
            return await self.transactions.run(action, resolve)

    async def append(self, migration_id: int, items: tuple[MigrationItemData, ...]) -> int:
        identifier(migration_id)
        if (
            not items
            or len(items) > 1000
            or len({(item.source_table, item.source_key) for item in items}) != len(items)
        ):
            raise ValueError("移行監査batchは重複なしの1..1000件で指定してください")
        ordered = sorted(items, key=lambda item: (item.source_table, item.source_key))

        def matches(row: MigrationItem, item: MigrationItemData) -> bool:
            return (
                row.source_values == item.source_values
                and row.target_keys == item.target_keys
                and row.applied_at == item.applied_at
            )

        async def resolve(session: AsyncSession) -> Resolution[int]:
            for item in ordered:
                row = await session.get(MigrationItem, (migration_id, item.source_table, item.source_key))
                if row is None:
                    return Resolution(False)
                if not matches(row, item):
                    raise ValueError("同じ原本キーの値は変更できません")
            return Resolution(True, len(ordered))

        async def action(session: AsyncSession) -> int:
            run = await session.get(MigrationRun, migration_id, with_for_update=True)
            if run is None:
                raise ValueError("移行監査runが存在しません")
            for item in ordered:
                await ensure(
                    session,
                    MigrationItem,
                    {
                        "migration_id": migration_id,
                        "source_table": item.source_table,
                        "source_key": item.source_key,
                        "source_values": item.source_values,
                        "target_keys": item.target_keys,
                        "applied_at": item.applied_at,
                    },
                    "migration_id",
                )
                row = await session.get(
                    MigrationItem, (migration_id, item.source_table, item.source_key), with_for_update=True
                )
                if row is None or not matches(row, item):
                    raise ValueError("同じ原本キーの値は変更できません")
            return len(ordered)

        async with self.gate.exclusive():
            return await self.transactions.run(action, resolve)
