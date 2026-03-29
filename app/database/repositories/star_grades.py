from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.features.leveling.domain.math_calculation import calculation_grade, calculation_prestige, calculation_shard


@dataclass
class StarGradeData:
    user_id: int
    prestige: int
    grade: int
    shard: int
    text_shard: int
    voice_shard: int
    bonus_shard: int
    created_at: datetime
    updated_at: datetime


@dataclass
class StarGradeRankingData(StarGradeData):
    ranking: int


class StarGrades:
    def __init__(self, db):
        self.db = db

    async def create_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SHOW TABLES LIKE 'star_grades'")
                if len(await cur.fetchall()) > 0:
                    return
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS star_grades (user_id BIGINT UNSIGNED PRIMARY KEY,"
                    "prestige TINYINT UNSIGNED NOT NULL, grade TINYINT UNSIGNED NOT NULL,"
                    "shard INT UNSIGNED NOT NULL, text_shard INT UNSIGNED NOT NULL,"
                    "voice_shard INT UNSIGNED NOT NULL, bonus_shard INT UNSIGNED NOT NULL,"
                    "created_at DATETIME DEFAULT CURRENT_TIMESTAMP, "
                    "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP on update CURRENT_TIMESTAMP)"
                )
                await conn.commit()

    async def drop_table(self) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DROP TABLE IF EXISTS star_grades")
                await conn.commit()

    async def get_star_grade(self, user_id: int) -> StarGradeData | None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM star_grades WHERE user_id = %s", (user_id,))
                result = await cur.fetchone()
                await conn.commit()
        return StarGradeData(*result) if result else None

    async def get_star_grade_lock(self, conn: Any, user_id: int) -> StarGradeData | None:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM star_grades WHERE user_id = %s FOR UPDATE", (user_id,))
            result = await cur.fetchone()
        return StarGradeData(*result) if result else None

    async def get_star_grade_ranking(
        self, show_user_id: int | None = None, limit: int | None = None
    ) -> list[StarGradeRankingData] | StarGradeRankingData | None:
        if show_user_id is not None:
            async with self.db.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        SELECT *,
                            (
                                SELECT COUNT(0)
                                FROM star_grades
                                WHERE star_grades.prestige > star_grades1.prestige
                                    OR (
                                        star_grades.prestige = star_grades1.prestige
                                        AND star_grades.grade > star_grades1.grade
                                    )
                                    OR (
                                        star_grades.prestige = star_grades1.prestige
                                        AND star_grades.grade = star_grades1.grade
                                        AND star_grades.shard > star_grades1.shard
                                    )
                            ) + 1 AS ranking
                        FROM star_grades AS star_grades1
                        WHERE star_grades1.user_id = %s
                        """,
                        (show_user_id,),
                    )
                    result = await cur.fetchone()
                    await conn.commit()
            return StarGradeRankingData(*result) if result else None

        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if limit is None or limit < 1:
                    await cur.execute(
                        """
                        SELECT *,
                            RANK() OVER (ORDER BY prestige DESC, grade DESC, shard DESC) AS ranking
                        FROM star_grades
                        """
                    )
                else:
                    await cur.execute(
                        """
                        SELECT *,
                            RANK() OVER (ORDER BY prestige DESC, grade DESC, shard DESC) AS ranking
                        FROM star_grades
                        LIMIT %s
                        """,
                        (limit,),
                    )
                result = await cur.fetchall()
                await conn.commit()
        return [StarGradeRankingData(*star_grade_data) for star_grade_data in result]

    async def create_star_grade(
        self,
        user_id: int,
        prestige: int = 0,
        grade: int = 0,
        shard: int = 0,
        text_shard: int = 0,
        voice_shard: int = 0,
        bonus_shard: int = 0,
    ) -> StarGradeData:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO star_grades (
                        user_id, prestige, grade, shard, text_shard, voice_shard, bonus_shard
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, prestige, grade, shard, text_shard, voice_shard, bonus_shard),
                )
                await conn.commit()
        return StarGradeData(
            user_id, prestige, grade, shard, text_shard, voice_shard, bonus_shard, datetime.now(), datetime.now()
        )

    async def create_star_grade_lock(
        self,
        conn: Any,
        user_id: int,
        prestige: int = 0,
        grade: int = 0,
        shard: int = 0,
        text_shard: int = 0,
        voice_shard: int = 0,
        bonus_shard: int = 0,
    ) -> StarGradeData:
        await conn.rollback()
        await self.create_star_grade(user_id, prestige, grade, shard, text_shard, voice_shard, bonus_shard)
        return await self.get_star_grade_lock(conn, user_id)

    async def _write_state(self, data: StarGradeData) -> None:
        async with self.db.pool.acquire() as conn:
            await self._write_state_lock(conn, data)
            await conn.commit()

    async def _write_state_lock(self, conn: Any, data: StarGradeData) -> None:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE star_grades
                SET prestige = %s,
                    grade = %s,
                    shard = %s,
                    text_shard = %s,
                    voice_shard = %s,
                    bonus_shard = %s
                WHERE user_id = %s
                """,
                (
                    data.prestige,
                    data.grade,
                    data.shard,
                    data.text_shard,
                    data.voice_shard,
                    data.bonus_shard,
                    data.user_id,
                ),
            )

    def _updated(
        self,
        star_grade_data: StarGradeData,
        *,
        prestige: int,
        grade: int,
        shard: int,
        text_shard: int | None = None,
        voice_shard: int | None = None,
        bonus_shard: int | None = None,
    ) -> StarGradeData:
        return StarGradeData(
            star_grade_data.user_id,
            prestige,
            grade,
            shard,
            star_grade_data.text_shard if text_shard is None else text_shard,
            star_grade_data.voice_shard if voice_shard is None else voice_shard,
            star_grade_data.bonus_shard if bonus_shard is None else bonus_shard,
            star_grade_data.created_at,
            datetime.now(),
        )

    def _consume_shards(
        self, star_grade_data: StarGradeData, removed_shard: int, *, prestige: int, grade: int, shard: int
    ) -> StarGradeData:
        bonus = star_grade_data.bonus_shard
        text = star_grade_data.text_shard
        voice = star_grade_data.voice_shard

        remaining = removed_shard
        take = min(bonus, remaining)
        bonus -= take
        remaining -= take
        take = min(text, remaining)
        text -= take
        remaining -= take
        take = min(voice, remaining)
        voice -= take
        remaining -= take

        if remaining > 0:
            prestige = 0
            grade = 0
            shard = 0
            text = 0
            voice = 0
            bonus = 0

        return self._updated(
            star_grade_data,
            prestige=prestige,
            grade=grade,
            shard=shard,
            text_shard=text,
            voice_shard=voice,
            bonus_shard=bonus,
        )

    async def add_prestige(
        self, star_grade_data: StarGradeData, add_prestige: int, shard_type: str = "ボーナス"
    ) -> tuple[StarGradeData, int, int, int]:
        prestige, grade, shard, grade_up_amount, prestige_amount, added_shard = calculation_prestige(
            star_grade_data.prestige, star_grade_data.grade, star_grade_data.shard, add_prestige
        )
        updated = self._updated(star_grade_data, prestige=prestige, grade=grade, shard=shard)
        if shard_type == "テキスト":
            updated.text_shard += added_shard
        elif shard_type == "ボイス":
            updated.voice_shard += added_shard
        else:
            updated.bonus_shard += added_shard
        await self._write_state(updated)
        return updated, grade_up_amount, prestige_amount, added_shard

    async def remove_prestige(
        self, star_grade_data: StarGradeData, remove_prestige: int
    ) -> tuple[StarGradeData, int, int, int]:
        prestige, grade, shard, grade_up_amount, prestige_amount, removed_shard = calculation_prestige(
            star_grade_data.prestige, star_grade_data.grade, star_grade_data.shard, -remove_prestige
        )
        updated = self._consume_shards(
            star_grade_data,
            removed_shard,
            prestige=prestige,
            grade=grade,
            shard=shard,
        )
        await self._write_state(updated)
        return updated, grade_up_amount, prestige_amount, removed_shard

    async def add_grade(
        self, star_grade_data: StarGradeData, add_grade: int, shard_type: str = "ボーナス"
    ) -> tuple[StarGradeData, int, int, int]:
        prestige, grade, shard, grade_up_amount, prestige_amount, added_shard = calculation_grade(
            star_grade_data.prestige, star_grade_data.grade, star_grade_data.shard, add_grade
        )
        updated = self._updated(star_grade_data, prestige=prestige, grade=grade, shard=shard)
        if shard_type == "テキスト":
            updated.text_shard += added_shard
        elif shard_type == "ボイス":
            updated.voice_shard += added_shard
        else:
            updated.bonus_shard += added_shard
        await self._write_state(updated)
        return updated, grade_up_amount, prestige_amount, added_shard

    async def remove_grade(
        self, star_grade_data: StarGradeData, remove_grade: int
    ) -> tuple[StarGradeData, int, int, int]:
        prestige, grade, shard, grade_up_amount, prestige_amount, removed_shard = calculation_grade(
            star_grade_data.prestige, star_grade_data.grade, star_grade_data.shard, -remove_grade
        )
        updated = self._consume_shards(
            star_grade_data,
            removed_shard,
            prestige=prestige,
            grade=grade,
            shard=shard,
        )
        await self._write_state(updated)
        return updated, grade_up_amount, prestige_amount, removed_shard

    async def add_text_shard(self, star_grade_data: StarGradeData, add_shard: int) -> tuple[StarGradeData, int, int]:
        prestige, grade, shard, grade_up_amount, prestige_amount = calculation_shard(
            star_grade_data.prestige, star_grade_data.grade, star_grade_data.shard, add_shard
        )
        updated = self._updated(
            star_grade_data,
            prestige=prestige,
            grade=grade,
            shard=shard,
            text_shard=star_grade_data.text_shard + add_shard,
        )
        await self._write_state(updated)
        return updated, grade_up_amount, prestige_amount

    async def add_text_shard_lock(
        self, conn: Any, star_grade_data: StarGradeData, add_shard: int
    ) -> tuple[StarGradeData, int, int]:
        prestige, grade, shard, grade_up_amount, prestige_amount = calculation_shard(
            star_grade_data.prestige, star_grade_data.grade, star_grade_data.shard, add_shard
        )
        updated = self._updated(
            star_grade_data,
            prestige=prestige,
            grade=grade,
            shard=shard,
            text_shard=star_grade_data.text_shard + add_shard,
        )
        await self._write_state_lock(conn, updated)
        return updated, grade_up_amount, prestige_amount

    async def remove_text_shard(
        self, star_grade_data: StarGradeData, remove_shard: int
    ) -> tuple[StarGradeData, int, int]:
        remove_shard = min(remove_shard, star_grade_data.text_shard)
        prestige, grade, shard, grade_up_amount, prestige_amount = calculation_shard(
            star_grade_data.prestige, star_grade_data.grade, star_grade_data.shard, -remove_shard
        )
        updated = self._updated(
            star_grade_data,
            prestige=prestige,
            grade=grade,
            shard=shard,
            text_shard=star_grade_data.text_shard - remove_shard,
        )
        await self._write_state(updated)
        return updated, grade_up_amount, prestige_amount

    async def add_voice_shard(self, star_grade_data: StarGradeData, add_shard: int) -> tuple[StarGradeData, int, int]:
        prestige, grade, shard, grade_up_amount, prestige_amount = calculation_shard(
            star_grade_data.prestige, star_grade_data.grade, star_grade_data.shard, add_shard
        )
        updated = self._updated(
            star_grade_data,
            prestige=prestige,
            grade=grade,
            shard=shard,
            voice_shard=star_grade_data.voice_shard + add_shard,
        )
        await self._write_state(updated)
        return updated, grade_up_amount, prestige_amount

    async def add_voice_shard_lock(
        self, conn: Any, star_grade_data: StarGradeData, add_shard: int
    ) -> tuple[StarGradeData, int, int]:
        prestige, grade, shard, grade_up_amount, prestige_amount = calculation_shard(
            star_grade_data.prestige, star_grade_data.grade, star_grade_data.shard, add_shard
        )
        updated = self._updated(
            star_grade_data,
            prestige=prestige,
            grade=grade,
            shard=shard,
            voice_shard=star_grade_data.voice_shard + add_shard,
        )
        await self._write_state_lock(conn, updated)
        return updated, grade_up_amount, prestige_amount

    async def remove_voice_shard(
        self, star_grade_data: StarGradeData, remove_shard: int
    ) -> tuple[StarGradeData, int, int]:
        remove_shard = min(remove_shard, star_grade_data.voice_shard)
        prestige, grade, shard, grade_up_amount, prestige_amount = calculation_shard(
            star_grade_data.prestige, star_grade_data.grade, star_grade_data.shard, -remove_shard
        )
        updated = self._updated(
            star_grade_data,
            prestige=prestige,
            grade=grade,
            shard=shard,
            voice_shard=star_grade_data.voice_shard - remove_shard,
        )
        await self._write_state(updated)
        return updated, grade_up_amount, prestige_amount

    async def add_bonus_shard(self, star_grade_data: StarGradeData, add_shard: int) -> tuple[StarGradeData, int, int]:
        prestige, grade, shard, grade_up_amount, prestige_amount = calculation_shard(
            star_grade_data.prestige, star_grade_data.grade, star_grade_data.shard, add_shard
        )
        updated = self._updated(
            star_grade_data,
            prestige=prestige,
            grade=grade,
            shard=shard,
            bonus_shard=star_grade_data.bonus_shard + add_shard,
        )
        await self._write_state(updated)
        return updated, grade_up_amount, prestige_amount

    async def add_bonus_shard_lock(
        self, conn: Any, star_grade_data: StarGradeData, add_shard: int
    ) -> tuple[StarGradeData, int, int]:
        prestige, grade, shard, grade_up_amount, prestige_amount = calculation_shard(
            star_grade_data.prestige, star_grade_data.grade, star_grade_data.shard, add_shard
        )
        updated = self._updated(
            star_grade_data,
            prestige=prestige,
            grade=grade,
            shard=shard,
            bonus_shard=star_grade_data.bonus_shard + add_shard,
        )
        await self._write_state_lock(conn, updated)
        return updated, grade_up_amount, prestige_amount

    async def remove_bonus_shard(
        self, star_grade_data: StarGradeData, remove_shard: int
    ) -> tuple[StarGradeData, int, int]:
        remove_shard = min(remove_shard, star_grade_data.bonus_shard)
        prestige, grade, shard, grade_up_amount, prestige_amount = calculation_shard(
            star_grade_data.prestige, star_grade_data.grade, star_grade_data.shard, -remove_shard
        )
        updated = self._updated(
            star_grade_data,
            prestige=prestige,
            grade=grade,
            shard=shard,
            bonus_shard=star_grade_data.bonus_shard - remove_shard,
        )
        await self._write_state(updated)
        return updated, grade_up_amount, prestige_amount

    async def delete_star_grade(self, user_id: int) -> None:
        async with self.db.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("DELETE FROM star_grades WHERE user_id = %s", (user_id,))
                await conn.commit()
