from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class XPBoostData:
    role_id: int
    name: str
    boost_amount: int
    boost_end_time: datetime | None
    created_at: datetime
    updated_at: datetime


class XPBoosts:
    def __init__(self, db):
        self.db = db

    async def create_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SHOW TABLES LIKE 'xp_boosts'")
                if len(await cur.fetchall()) > 0:
                    return
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS xp_boosts (role_id BIGINT UNSIGNED PRIMARY KEY,"
                    "name VARCHAR(100) NOT NULL,"
                    "boost_amount INT UNSIGNED NOT NULL, boost_end_time DATETIME,"
                    "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP)"
                )
                await conn.commit()

    async def drop_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DROP TABLE IF EXISTS xp_boosts")
                await conn.commit()

    async def get_xp_boosts(self) -> list[XPBoostData]:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM xp_boosts")
                result = await cur.fetchall()
                await conn.commit()
        return [XPBoostData(*xp_boost) for xp_boost in result]

    async def get_xp_boost(self, role_id: int) -> XPBoostData | None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM xp_boosts WHERE role_id = %s", (role_id,))
                result = await cur.fetchone()
                await conn.commit()
        return XPBoostData(*result) if result else None

    async def create_xp_boost(
        self, role_id: int, name: str, boost_amount: int, boost_end_time: datetime | None
    ) -> None:
        if boost_end_time is not None:
            boost_end_time = boost_end_time.strftime("%Y-%m-%d %H:%M:%S.%f")

        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO xp_boosts (role_id, name, boost_amount, boost_end_time) VALUES (%s, %s, %s, %s)",
                    (role_id, name, boost_amount, boost_end_time),
                )
                await conn.commit()

    async def delete_xp_boost(self, role_id: int) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM xp_boosts WHERE role_id = %s ", (role_id,))
                await conn.commit()

    async def delete_expired_xp_boosts(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM xp_boosts WHERE boost_end_time < NOW()")
                await conn.commit()
