from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime


@dataclass
class UserBirthdayData:
    user_id: int
    date: Date
    created_at: datetime
    updated_at: datetime


class UserBirthdays:
    def __init__(self, db):
        self.db = db

    async def create_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SHOW TABLES LIKE 'user_birthdays'")
                if len(await cur.fetchall()) > 0:
                    return
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS user_birthdays (user_id BIGINT UNSIGNED PRIMARY KEY, date DATE,"
                    "created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
                    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP)"
                )
                await conn.commit()

    async def drop_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DROP TABLE IF EXISTS user_birthdays")
                await conn.commit()

    async def get_user_data(self, user_id: int) -> UserBirthdayData | None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM user_birthdays WHERE user_id = %s", (user_id,))
                result = await cur.fetchone()
                await conn.commit()
        return UserBirthdayData(*result) if result else None

    async def get_user_data_by_date(self, date: Date) -> list[UserBirthdayData]:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM user_birthdays WHERE date = %s", (date,))
                raw_data = await cur.fetchall()
                await conn.commit()
                return [UserBirthdayData(*data) for data in raw_data]

    async def get_sorted_all_user_data(self) -> list[UserBirthdayData]:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM user_birthdays")
                raw_data = await cur.fetchall()
                await conn.commit()
        data = [UserBirthdayData(*raw) for raw in raw_data]
        return sorted(data, key=lambda x: (x.date.month, x.date.day))

    async def upsert_data(self, user_id: int, date: Date) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO user_birthdays (user_id, date) VALUES (%s, %s) AS new "
                    "ON DUPLICATE KEY UPDATE date = new.date",
                    (user_id, date),
                )
                await conn.commit()

    async def delete_data(self, user_id: int) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM user_birthdays WHERE user_id = %s", (user_id,))
                await conn.commit()
