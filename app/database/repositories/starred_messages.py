from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class StarredMessageData:
    starred_message_id: int
    starboard_message_id: int
    star_amount: int
    user_id: int
    starred_message_channel_id: int
    created_at: datetime
    updated_at: datetime


@dataclass
class StarAmountRankingData:
    user_id: int
    star_amount: int


class StarredMessages:
    def __init__(self, db):
        self.db = db

    async def create_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SHOW TABLES LIKE 'starred_messages'")
                if len(await cur.fetchall()) > 0:
                    return
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS starred_messages (starred_message_id BIGINT UNSIGNED PRIMARY KEY,"
                    "starboard_message_id BIGINT UNSIGNED, star_amount INT UNSIGNED, user_id BIGINT UNSIGNED,"
                    "starred_message_channel_id BIGINT UNSIGNED,"
                    "created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
                    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP)"
                )
                await conn.commit()

    async def drop_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DROP TABLE IF EXISTS starred_messages")
                await conn.commit()

    async def get_starred_message(self, message_id: int) -> StarredMessageData | None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM starred_messages WHERE starred_message_id = %s", (message_id,))
                raw_message = await cur.fetchone()
                await conn.commit()
                return StarredMessageData(*raw_message) if raw_message else None

    async def get_random_starred_message(self) -> StarredMessageData | None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM starred_messages ORDER BY RAND() LIMIT 1")
                raw_message = await cur.fetchone()
                await conn.commit()
                return StarredMessageData(*raw_message) if raw_message else None

    async def get_starred_message_ranking(self, limit: int = 10) -> list[StarredMessageData]:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM starred_messages ORDER BY star_amount DESC LIMIT %s", (limit,))
                starred_messages = await cur.fetchall()
                await conn.commit()
                return [StarredMessageData(*starred_message) for starred_message in starred_messages]

    async def get_star_amount_ranking(self, limit: int = 10) -> list[StarAmountRankingData]:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT user_id, SUM(star_amount)
                    FROM starred_messages
                    GROUP BY user_id
                    ORDER BY SUM(star_amount) DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                starred_messages = await cur.fetchall()
                await conn.commit()
                return [StarAmountRankingData(*starred_message) for starred_message in starred_messages]

    async def create_starred_message(
        self,
        message_id: int,
        starboard_message_id: int,
        star_amount: int,
        user_id: int,
        starred_message_channel_id: int,
    ) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO starred_messages (
                        starred_message_id,
                        starboard_message_id,
                        star_amount,
                        user_id,
                        starred_message_channel_id
                    ) VALUES (%s, %s, %s, %s, %s)
                    """,
                    (message_id, starboard_message_id, star_amount, user_id, starred_message_channel_id),
                )
                await conn.commit()

    async def set_star_amount(self, message_id: int, star_amount: int) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE starred_messages SET star_amount = %s WHERE starred_message_id = %s",
                    (star_amount, message_id),
                )
                await conn.commit()

    async def delete_starred_message(self, message_id: int) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM starred_messages WHERE starred_message_id = %s", (message_id,))
                await conn.commit()
