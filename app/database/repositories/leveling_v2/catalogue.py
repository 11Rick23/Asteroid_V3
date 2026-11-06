"""運用Guild固定とチャンネル名の保存。旧Bot設定は読まない。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database.models.leveling_v2 import Channel, Installation
from app.features.leveling.domain.numbers import identifier
from app.features.leveling.domain.periods import aware

from .locks import MutationGate
from .storage import ensure
from .transaction import Resolution, Transactions


@dataclass(frozen=True)
class InstallationData:
    guild_id: int
    ranking_started_at: datetime | None
    generation: int


@dataclass(frozen=True)
class ChannelData:
    channel_id: int
    name: str
    kind: str
    last_seen_at: datetime
    deleted_at: datetime | None


def channel_data(row: Channel) -> ChannelData:
    return ChannelData(row.channel_id, row.last_name, row.kind, row.last_seen_at, row.deleted_at)


class CatalogueRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession], gate: MutationGate) -> None:
        self.sessions = sessions
        self.gate = gate
        self.transactions = Transactions(sessions)

    async def install(self, guild_id: int, ranking_started_at: datetime) -> InstallationData:
        identifier(guild_id)
        aware(ranking_started_at)

        def result(row: Installation) -> InstallationData:
            if row.guild_id != guild_id or row.ranking_started_at != ranking_started_at:
                raise ValueError("保存済み運用Guildまたは集計開始日時と一致しません")
            return InstallationData(row.guild_id, row.ranking_started_at, row.active_schema_generation)

        async def action(session: AsyncSession) -> InstallationData:
            await ensure(
                session, Installation, {"id": 1, "guild_id": guild_id, "ranking_started_at": ranking_started_at}, "id"
            )
            row = (await session.scalars(select(Installation).where(Installation.id == 1).with_for_update())).one()
            return result(row)

        async def resolve(session: AsyncSession) -> Resolution[InstallationData]:
            row = await session.get(Installation, 1)
            return Resolution(row is not None, None if row is None else result(row))

        async with self.gate.exclusive():
            return await self.transactions.run(action, resolve)

    async def get_channel(self, channel_id: int) -> ChannelData | None:
        identifier(channel_id)
        async with self.sessions() as session:
            row = await session.get(Channel, channel_id)
            return None if row is None else channel_data(row)

    async def observe_channel(
        self,
        channel_id: int,
        name: str,
        kind: str,
        observed_at: datetime,
        *,
        deleted: bool = False,
    ) -> ChannelData:
        identifier(channel_id)
        aware(observed_at)
        if not name or len(name) > 100 or kind not in ("text", "voice") or type(deleted) is not bool:
            raise ValueError("チャンネル情報が不正です")

        async def action(session: AsyncSession) -> ChannelData:
            await ensure(
                session,
                Channel,
                {
                    "channel_id": channel_id,
                    "last_name": name,
                    "kind": kind,
                    "last_seen_at": observed_at,
                    "deleted_at": observed_at if deleted else None,
                },
                "channel_id",
            )
            row = (
                await session.scalars(select(Channel).where(Channel.channel_id == channel_id).with_for_update())
            ).one()
            if row.kind != kind:
                raise ValueError("チャンネル種別を変更できません")
            if row.last_seen_at == observed_at and (row.last_name != name or (row.deleted_at is not None) != deleted):
                raise ValueError("同じ観測時刻のチャンネル情報が矛盾しています")
            if row.last_seen_at <= observed_at:
                row.last_name = name
                row.last_seen_at = observed_at
                row.deleted_at = observed_at if deleted else None
            return channel_data(row)

        async def resolve(session: AsyncSession) -> Resolution[ChannelData]:
            row = await session.get(Channel, channel_id)
            found = (
                row is not None
                and row.kind == kind
                and (
                    row.last_seen_at > observed_at
                    or (
                        row.last_seen_at == observed_at
                        and row.last_name == name
                        and (row.deleted_at is not None) == deleted
                    )
                )
            )
            return Resolution(found, None if row is None else channel_data(row))

        async with self.gate.exclusive():
            return await self.transactions.run(action, resolve)
