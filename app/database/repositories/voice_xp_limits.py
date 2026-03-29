from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import update, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.voice_xp_limits import VoiceXPLimitModel


@dataclass
class VoiceXPLimitData:
    user_id: int
    voice_shard: int
    bonus_shard: int
    voice_power: int
    half_notify: bool
    full_notify: bool
    created_at: datetime
    updated_at: datetime


class VoiceXPLimits:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _to_data(model: VoiceXPLimitModel | None) -> VoiceXPLimitData | None:
        if model is None:
            return None
        return VoiceXPLimitData(
            user_id=model.user_id,
            voice_shard=model.voice_shard,
            bonus_shard=model.bonus_shard,
            voice_power=model.voice_power,
            half_notify=model.half_notify,
            full_notify=model.full_notify,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def create_table(self) -> None:
        async with self.db.engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: VoiceXPLimitModel.__table__.create(sync_conn, checkfirst=True))

    async def drop_table(self) -> None:
        async with self.db.engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: VoiceXPLimitModel.__table__.drop(sync_conn, checkfirst=True))

    async def get_voice_xp_limit(self, user_id: int) -> VoiceXPLimitData | None:
        async with self.db.session() as session:
            return self._to_data(await session.get(VoiceXPLimitModel, user_id))

    async def get_voice_xp_limit_lock(self, session: AsyncSession, user_id: int) -> VoiceXPLimitData | None:
        stmt = select(VoiceXPLimitModel).where(VoiceXPLimitModel.user_id == user_id).with_for_update()
        return self._to_data(await session.scalar(stmt))

    async def create_voice_xp_limit(
        self,
        user_id: int,
        voice_shard: int = 0,
        bonus_shard: int = 0,
        voice_power: int = 0,
        half_notify: bool = False,
        full_notify: bool = False,
    ) -> VoiceXPLimitData:
        async with self.db.session() as session:
            data = await self.create_voice_xp_limit_lock(
                session,
                user_id,
                voice_shard,
                bonus_shard,
                voice_power,
                half_notify,
                full_notify,
            )
            await session.commit()
            return data

    async def create_voice_xp_limit_lock(
        self,
        session: AsyncSession,
        user_id: int,
        voice_shard: int = 0,
        bonus_shard: int = 0,
        voice_power: int = 0,
        half_notify: bool = False,
        full_notify: bool = False,
    ) -> VoiceXPLimitData:
        now = datetime.now()
        session.add(
            VoiceXPLimitModel(
                user_id=user_id,
                voice_shard=voice_shard,
                bonus_shard=bonus_shard,
                voice_power=voice_power,
                half_notify=half_notify,
                full_notify=full_notify,
            )
        )
        await session.flush()
        return VoiceXPLimitData(
            user_id, voice_shard, bonus_shard, voice_power, half_notify, full_notify, now, now
        )

    def _updated(
        self,
        data: VoiceXPLimitData,
        *,
        voice_shard: int | None = None,
        bonus_shard: int | None = None,
        voice_power: int | None = None,
        half_notify: bool | None = None,
        full_notify: bool | None = None,
    ) -> VoiceXPLimitData:
        return VoiceXPLimitData(
            data.user_id,
            data.voice_shard if voice_shard is None else voice_shard,
            data.bonus_shard if bonus_shard is None else bonus_shard,
            data.voice_power if voice_power is None else voice_power,
            data.half_notify if half_notify is None else half_notify,
            data.full_notify if full_notify is None else full_notify,
            data.created_at,
            datetime.now(),
        )

    async def _write_state(self, data: VoiceXPLimitData) -> None:
        async with self.db.session() as session:
            await self._write_state_lock(session, data)
            await session.commit()

    async def _write_state_lock(self, session: AsyncSession, data: VoiceXPLimitData) -> None:
        model = await session.get(VoiceXPLimitModel, data.user_id)
        if model is None:
            return
        model.voice_shard = data.voice_shard
        model.bonus_shard = data.bonus_shard
        model.voice_power = data.voice_power
        model.half_notify = data.half_notify
        model.full_notify = data.full_notify

    def _apply_limit(
        self, current: int, add_value: int, limit: int, half_notify: bool, full_notify: bool
    ) -> tuple[int, bool, bool]:
        if (current + add_value) >= limit:
            add_value = max(limit - current, 0)
            return add_value, True, True
        if (current + add_value) >= (limit / 2):
            return add_value, True, full_notify
        return add_value, half_notify, full_notify

    async def add_voice_shard(
        self, voice_xp_limit_data: VoiceXPLimitData, add_shard: int, limit: int
    ) -> tuple[VoiceXPLimitData, bool, bool]:
        current = voice_xp_limit_data.voice_shard + voice_xp_limit_data.bonus_shard
        add_shard, half_notify, full_notify = self._apply_limit(
            current, add_shard, limit, voice_xp_limit_data.half_notify, voice_xp_limit_data.full_notify
        )
        updated = self._updated(
            voice_xp_limit_data,
            voice_shard=voice_xp_limit_data.voice_shard + add_shard,
            half_notify=half_notify,
            full_notify=full_notify,
        )
        await self._write_state(updated)
        return updated, half_notify, full_notify

    async def add_voice_shard_lock(
        self, session: AsyncSession, voice_xp_limit_data: VoiceXPLimitData, add_shard: int, limit: int
    ) -> tuple[VoiceXPLimitData, bool, bool]:
        current = voice_xp_limit_data.voice_shard + voice_xp_limit_data.bonus_shard
        add_shard, half_notify, full_notify = self._apply_limit(
            current, add_shard, limit, voice_xp_limit_data.half_notify, voice_xp_limit_data.full_notify
        )
        updated = self._updated(
            voice_xp_limit_data,
            voice_shard=voice_xp_limit_data.voice_shard + add_shard,
            half_notify=half_notify,
            full_notify=full_notify,
        )
        await self._write_state_lock(session, updated)
        return updated, half_notify, full_notify

    async def add_bonus_shard(
        self, voice_xp_limit_data: VoiceXPLimitData, add_shard: int, limit: int
    ) -> tuple[VoiceXPLimitData, bool, bool]:
        current = voice_xp_limit_data.voice_shard + voice_xp_limit_data.bonus_shard
        add_shard, half_notify, full_notify = self._apply_limit(
            current, add_shard, limit, voice_xp_limit_data.half_notify, voice_xp_limit_data.full_notify
        )
        updated = self._updated(
            voice_xp_limit_data,
            bonus_shard=voice_xp_limit_data.bonus_shard + add_shard,
            half_notify=half_notify,
            full_notify=full_notify,
        )
        await self._write_state(updated)
        return updated, half_notify, full_notify

    async def add_bonus_shard_lock(
        self, session: AsyncSession, voice_xp_limit_data: VoiceXPLimitData, add_shard: int, limit: int
    ) -> tuple[VoiceXPLimitData, bool, bool]:
        current = voice_xp_limit_data.voice_shard + voice_xp_limit_data.bonus_shard
        add_shard, half_notify, full_notify = self._apply_limit(
            current, add_shard, limit, voice_xp_limit_data.half_notify, voice_xp_limit_data.full_notify
        )
        updated = self._updated(
            voice_xp_limit_data,
            bonus_shard=voice_xp_limit_data.bonus_shard + add_shard,
            half_notify=half_notify,
            full_notify=full_notify,
        )
        await self._write_state_lock(session, updated)
        return updated, half_notify, full_notify

    async def add_voice_power(
        self, voice_xp_limit_data: VoiceXPLimitData, add_power: int, limit: int
    ) -> tuple[VoiceXPLimitData, bool, bool]:
        add_power, half_notify, full_notify = self._apply_limit(
            voice_xp_limit_data.voice_power,
            add_power,
            limit,
            voice_xp_limit_data.half_notify,
            voice_xp_limit_data.full_notify,
        )
        updated = self._updated(
            voice_xp_limit_data,
            voice_power=voice_xp_limit_data.voice_power + add_power,
            half_notify=half_notify,
            full_notify=full_notify,
        )
        await self._write_state(updated)
        return updated, half_notify, full_notify

    async def add_voice_power_lock(
        self, session: AsyncSession, voice_xp_limit_data: VoiceXPLimitData, add_power: int, limit: int
    ) -> tuple[VoiceXPLimitData, bool, bool]:
        add_power, half_notify, full_notify = self._apply_limit(
            voice_xp_limit_data.voice_power,
            add_power,
            limit,
            voice_xp_limit_data.half_notify,
            voice_xp_limit_data.full_notify,
        )
        updated = self._updated(
            voice_xp_limit_data,
            voice_power=voice_xp_limit_data.voice_power + add_power,
            half_notify=half_notify,
            full_notify=full_notify,
        )
        await self._write_state_lock(session, updated)
        return updated, half_notify, full_notify

    async def delete_voice_xp_limit(self, user_id: int) -> None:
        async with self.db.session() as session:
            await self.delete_voice_xp_limit_lock(session, user_id)
            await session.commit()

    async def delete_voice_xp_limit_lock(self, session: AsyncSession, user_id: int) -> None:
        model = await session.get(VoiceXPLimitModel, user_id)
        if model is not None:
            await session.delete(model)

    async def reset_voice_power(self) -> None:
        async with self.db.session() as session:
            await session.execute(update(VoiceXPLimitModel).values(voice_power=0))
            await session.commit()
