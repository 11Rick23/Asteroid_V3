from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class GivenStarData:
    user_id: int
    given_star_amount: int
    created_at: datetime
    updated_at: datetime


class GivenStars:
    def __init__(self, db):
        self.db = db

    async def create_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SHOW TABLES LIKE 'given_stars'")
                if len(await cur.fetchall()) > 0:
                    return
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS given_stars (user_id BIGINT UNSIGNED PRIMARY KEY,"
                    "given_star_amount INT UNSIGNED,"
                    "created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
                    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP)"
                )
                await conn.commit()

    async def drop_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DROP TABLE IF EXISTS given_stars")
                await conn.commit()

    async def get_given_star(self, user_id: int) -> GivenStarData | None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM given_stars WHERE user_id = %s", (user_id,))
                given_star = await cur.fetchone()
                await conn.commit()
                return GivenStarData(*given_star) if given_star else None

    async def get_given_star_ranking(self, limit: int = 10) -> list[GivenStarData]:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM given_stars ORDER BY given_star_amount DESC LIMIT %s", (limit,))
                given_stars = await cur.fetchall()
                await conn.commit()
                return [GivenStarData(*given_star) for given_star in given_stars]

    async def create_given_star(self, user_id: int, given_star_amount: int = 1) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO given_stars (user_id, given_star_amount) VALUES (%s, %s)",
                    (user_id, given_star_amount),
                )
                await conn.commit()

    async def add_given_star(self, user_id: int, given_star_amount: int = 1) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE given_stars SET given_star_amount = given_star_amount + %s WHERE user_id = %s",
                    (given_star_amount, user_id),
                )
                await conn.commit()

    async def remove_given_star(self, user_id: int, given_star_amount: int = 1) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE given_stars SET given_star_amount = given_star_amount - %s WHERE user_id = %s",
                    (given_star_amount, user_id),
                )
                await conn.commit()
