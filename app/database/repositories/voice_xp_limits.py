from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


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

    async def create_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SHOW TABLES LIKE 'voice_xp_limits'")
                if len(await cur.fetchall()) > 0:
                    return
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS voice_xp_limits (user_id BIGINT UNSIGNED PRIMARY KEY,"
                    "voice_shard INT UNSIGNED NOT NULL, bonus_shard INT UNSIGNED NOT NULL,"
                    "voice_power INT UNSIGNED NOT NULL,"
                    "half_notify BOOL NOT NULL, full_notify BOOL NOT NULL,"
                    "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP)"
                )
                await conn.commit()

    async def drop_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DROP TABLE IF EXISTS voice_xp_limits")
                await conn.commit()

    async def get_voice_xp_limit(self, user_id: int) -> VoiceXPLimitData | None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM voice_xp_limits WHERE user_id = %s", (user_id,))
                result = await cur.fetchone()
                await conn.commit()
        return VoiceXPLimitData(*result) if result else None

    async def get_voice_xp_limit_lock(self, conn: Any, user_id: int) -> VoiceXPLimitData | None:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM voice_xp_limits WHERE user_id = %s FOR UPDATE", (user_id,))
            result = await cur.fetchone()
        return VoiceXPLimitData(*result) if result else None

    async def create_voice_xp_limit(
        self,
        user_id: int,
        voice_shard: int = 0,
        bonus_shard: int = 0,
        voice_power: int = 0,
        half_notify: bool = False,
        full_notify: bool = False,
    ) -> VoiceXPLimitData:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO voice_xp_limits (
                        user_id, voice_shard, bonus_shard, voice_power, half_notify, full_notify
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, voice_shard, bonus_shard, voice_power, half_notify, full_notify),
                )
                await conn.commit()
        return VoiceXPLimitData(
            user_id, voice_shard, bonus_shard, voice_power, half_notify, full_notify, datetime.now(), datetime.now()
        )

    async def create_voice_xp_limit_lock(
        self,
        conn: Any,
        user_id: int,
        voice_shard: int = 0,
        bonus_shard: int = 0,
        voice_power: int = 0,
        half_notify: bool = False,
        full_notify: bool = False,
    ) -> VoiceXPLimitData:
        await conn.rollback()
        await self.create_voice_xp_limit(user_id, voice_shard, bonus_shard, voice_power, half_notify, full_notify)
        return await self.get_voice_xp_limit_lock(conn, user_id)

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
        async with self.db.pool.acquire() as conn:
            await self._write_state_lock(conn, data)
            await conn.commit()

    async def _write_state_lock(self, conn: Any, data: VoiceXPLimitData) -> None:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE voice_xp_limits
                SET voice_shard = %s,
                    bonus_shard = %s,
                    voice_power = %s,
                    half_notify = %s,
                    full_notify = %s
                WHERE user_id = %s
                """,
                (
                    data.voice_shard,
                    data.bonus_shard,
                    data.voice_power,
                    data.half_notify,
                    data.full_notify,
                    data.user_id,
                ),
            )

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
        self, conn: Any, voice_xp_limit_data: VoiceXPLimitData, add_shard: int, limit: int
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
        await self._write_state_lock(conn, updated)
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
        self, conn: Any, voice_xp_limit_data: VoiceXPLimitData, add_shard: int, limit: int
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
        await self._write_state_lock(conn, updated)
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
        self, conn: Any, voice_xp_limit_data: VoiceXPLimitData, add_power: int, limit: int
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
        await self._write_state_lock(conn, updated)
        return updated, half_notify, full_notify

    async def delete_voice_xp_limit(self, user_id: int) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM voice_xp_limits WHERE user_id = %s", (user_id,))
                await conn.commit()

    async def delete_voice_xp_limit_lock(self, conn: Any, user_id: int) -> None:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM voice_xp_limits WHERE user_id = %s", (user_id,))

    async def reset_voice_power(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("UPDATE voice_xp_limits SET voice_power = 0")
                await conn.commit()
