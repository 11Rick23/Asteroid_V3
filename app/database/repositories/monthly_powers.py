from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class MonthlyPowerData:
    user_id: int
    text_power: int
    voice_power: int
    created_at: datetime
    updated_at: datetime


@dataclass
class MonthlyPowerRankingData(MonthlyPowerData):
    ranking: int


class MonthlyPowers:
    def __init__(self, db):
        self.db = db

    async def create_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SHOW TABLES LIKE 'monthly_powers'")
                if len(await cur.fetchall()) > 0:
                    return
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS monthly_powers (user_id BIGINT UNSIGNED PRIMARY KEY,"
                    "text_power INT UNSIGNED NOT NULL, voice_power INT UNSIGNED NOT NULL,"
                    "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP)"
                )
                await conn.commit()

    async def drop_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DROP TABLE IF EXISTS monthly_powers")
                await conn.commit()

    async def truncate_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("TRUNCATE TABLE monthly_powers")
                await conn.commit()

    async def get_monthly_power(self, user_id: int) -> MonthlyPowerData | None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM monthly_powers WHERE user_id = %s", (user_id,))
                result = await cur.fetchone()
                await conn.commit()
        return MonthlyPowerData(*result) if result else None

    async def get_monthly_power_lock(self, conn: Any, user_id: int) -> MonthlyPowerData | None:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM monthly_powers WHERE user_id = %s FOR UPDATE", (user_id,))
            result = await cur.fetchone()
        return MonthlyPowerData(*result) if result else None

    async def get_monthly_power_ranking(
        self, show_user_id: int | None = None, limit: int | None = None
    ) -> list[MonthlyPowerRankingData] | MonthlyPowerRankingData | None:
        if show_user_id is not None:
            async with self.db.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT *,
                            (
                                SELECT COUNT(0)
                                FROM monthly_powers
                                WHERE (
                                    monthly_powers.text_power + monthly_powers.voice_power
                                ) > (
                                    monthly_powers1.text_power + monthly_powers1.voice_power
                                )
                            ) + 1 AS ranking
                        FROM monthly_powers AS monthly_powers1
                        WHERE monthly_powers1.user_id = %s
                        """,
                        (show_user_id,),
                    )
                    result = await cur.fetchone()
                    await conn.commit()
            return MonthlyPowerRankingData(*result) if result else None

        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if limit is None or limit < 1:
                    await cur.execute(
                        """
                        SELECT *,
                            RANK() OVER (ORDER BY (text_power + voice_power) DESC) AS ranking
                        FROM monthly_powers
                        """
                    )
                else:
                    await cur.execute(
                        """
                        SELECT *,
                            RANK() OVER (ORDER BY (text_power + voice_power) DESC) AS ranking
                        FROM monthly_powers
                        LIMIT %s
                        """,
                        (limit,),
                    )
                result = await cur.fetchall()
                await conn.commit()
        return [MonthlyPowerRankingData(*monthly_power_data) for monthly_power_data in result]

    async def create_monthly_power(self, user_id: int, text_power: int = 0, voice_power: int = 0) -> MonthlyPowerData:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO monthly_powers (user_id, text_power, voice_power) VALUES (%s, %s, %s)",
                    (user_id, text_power, voice_power),
                )
                await conn.commit()
        return MonthlyPowerData(user_id, text_power, voice_power, datetime.now(), datetime.now())

    async def create_monthly_power_lock(
        self, conn: Any, user_id: int, text_power: int = 0, voice_power: int = 0
    ) -> MonthlyPowerData:
        await conn.rollback()
        await self.create_monthly_power(user_id, text_power, voice_power)
        return await self.get_monthly_power_lock(conn, user_id)

    async def add_text_power(self, monthly_power_data: MonthlyPowerData, add_text_power: int) -> MonthlyPowerData:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE monthly_powers SET text_power = text_power + %s WHERE user_id = %s",
                    (add_text_power, monthly_power_data.user_id),
                )
                await conn.commit()
        return MonthlyPowerData(
            monthly_power_data.user_id,
            monthly_power_data.text_power + add_text_power,
            monthly_power_data.voice_power,
            monthly_power_data.created_at,
            datetime.now(),
        )

    async def add_text_power_lock(
        self, conn: Any, monthly_power_data: MonthlyPowerData, add_text_power: int
    ) -> MonthlyPowerData:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE monthly_powers SET text_power = text_power + %s WHERE user_id = %s",
                (add_text_power, monthly_power_data.user_id),
            )
        return MonthlyPowerData(
            monthly_power_data.user_id,
            monthly_power_data.text_power + add_text_power,
            monthly_power_data.voice_power,
            monthly_power_data.created_at,
            datetime.now(),
        )

    async def remove_text_power(
        self, monthly_power_data: MonthlyPowerData, remove_text_power: int
    ) -> MonthlyPowerData:
        if (monthly_power_data.text_power - remove_text_power) < 0:
            remove_text_power = monthly_power_data.text_power
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE monthly_powers SET text_power = text_power - %s WHERE user_id = %s",
                    (remove_text_power, monthly_power_data.user_id),
                )
                await conn.commit()
        return MonthlyPowerData(
            monthly_power_data.user_id,
            monthly_power_data.text_power - remove_text_power,
            monthly_power_data.voice_power,
            monthly_power_data.created_at,
            datetime.now(),
        )

    async def add_voice_power(self, monthly_power_data: MonthlyPowerData, add_voice_power: int) -> MonthlyPowerData:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE monthly_powers SET voice_power = voice_power + %s WHERE user_id = %s",
                    (add_voice_power, monthly_power_data.user_id),
                )
                await conn.commit()
        return MonthlyPowerData(
            monthly_power_data.user_id,
            monthly_power_data.text_power,
            monthly_power_data.voice_power + add_voice_power,
            monthly_power_data.created_at,
            datetime.now(),
        )

    async def add_voice_power_lock(
        self, conn: Any, monthly_power_data: MonthlyPowerData, add_voice_power: int
    ) -> MonthlyPowerData:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE monthly_powers SET voice_power = voice_power + %s WHERE user_id = %s",
                (add_voice_power, monthly_power_data.user_id),
            )
        return MonthlyPowerData(
            monthly_power_data.user_id,
            monthly_power_data.text_power,
            monthly_power_data.voice_power + add_voice_power,
            monthly_power_data.created_at,
            datetime.now(),
        )

    async def remove_voice_power(
        self, monthly_power_data: MonthlyPowerData, remove_voice_power: int
    ) -> MonthlyPowerData:
        if (monthly_power_data.voice_power - remove_voice_power) < 0:
            remove_voice_power = monthly_power_data.voice_power
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE monthly_powers SET voice_power = voice_power - %s WHERE user_id = %s",
                    (remove_voice_power, monthly_power_data.user_id),
                )
                await conn.commit()
        return MonthlyPowerData(
            monthly_power_data.user_id,
            monthly_power_data.text_power,
            monthly_power_data.voice_power - remove_voice_power,
            monthly_power_data.created_at,
            datetime.now(),
        )

    async def delete_monthly_power(self, user_id: int) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM monthly_powers WHERE user_id = %s", (user_id,))
                await conn.commit()
