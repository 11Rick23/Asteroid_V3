from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, overload

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.star_grades import StarGradeModel
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

    @staticmethod
    def _to_data(model: StarGradeModel | None) -> StarGradeData | None:
        if model is None:
            return None
        return StarGradeData(
            user_id=model.user_id,
            prestige=model.prestige,
            grade=model.grade,
            shard=model.shard,
            text_shard=model.text_shard,
            voice_shard=model.voice_shard,
            bonus_shard=model.bonus_shard,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_ranking_data(row: Any) -> StarGradeRankingData:
        return StarGradeRankingData(
            user_id=row.user_id,
            prestige=row.prestige,
            grade=row.grade,
            shard=row.shard,
            text_shard=row.text_shard,
            voice_shard=row.voice_shard,
            bonus_shard=row.bonus_shard,
            created_at=row.created_at,
            updated_at=row.updated_at,
            ranking=row.ranking,
        )

    @staticmethod
    def _ranking_subquery():
        ranking = func.rank().over(
            order_by=(StarGradeModel.prestige.desc(), StarGradeModel.grade.desc(), StarGradeModel.shard.desc())
        )
        return select(
            StarGradeModel.user_id.label("user_id"),
            StarGradeModel.prestige.label("prestige"),
            StarGradeModel.grade.label("grade"),
            StarGradeModel.shard.label("shard"),
            StarGradeModel.text_shard.label("text_shard"),
            StarGradeModel.voice_shard.label("voice_shard"),
            StarGradeModel.bonus_shard.label("bonus_shard"),
            StarGradeModel.created_at.label("created_at"),
            StarGradeModel.updated_at.label("updated_at"),
            ranking.label("ranking"),
        ).subquery()

    async def get_star_grade(self, user_id: int) -> StarGradeData | None:
        async with self.db.session() as session:
            return self._to_data(await session.get(StarGradeModel, user_id))

    async def get_star_grade_lock(self, session: AsyncSession, user_id: int) -> StarGradeData | None:
        stmt = select(StarGradeModel).where(StarGradeModel.user_id == user_id).with_for_update()
        return self._to_data(await session.scalar(stmt))

    @overload
    async def get_star_grade_ranking(
        self, show_user_id: int, limit: int | None = None
    ) -> StarGradeRankingData | None: ...

    @overload
    async def get_star_grade_ranking(
        self, show_user_id: None = None, limit: int | None = None
    ) -> list[StarGradeRankingData]: ...

    async def get_star_grade_ranking(
        self, show_user_id: int | None = None, limit: int | None = None
    ) -> list[StarGradeRankingData] | StarGradeRankingData | None:
        ranking_subquery = self._ranking_subquery()

        async with self.db.session() as session:
            if show_user_id is not None:
                stmt = select(ranking_subquery).where(ranking_subquery.c.user_id == show_user_id)
                result = await session.execute(stmt)
                row = result.one_or_none()
                return self._to_ranking_data(row) if row is not None else None

            stmt = select(ranking_subquery).order_by(
                ranking_subquery.c.prestige.desc(),
                ranking_subquery.c.grade.desc(),
                ranking_subquery.c.shard.desc(),
            )
            if limit is not None and limit > 0:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            return [self._to_ranking_data(row) for row in result.all()]

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
        async with self.db.session() as session:
            data = await self.create_star_grade_lock(
                session, user_id, prestige, grade, shard, text_shard, voice_shard, bonus_shard
            )
            await session.commit()
            return data

    async def create_star_grade_lock(
        self,
        session: AsyncSession,
        user_id: int,
        prestige: int = 0,
        grade: int = 0,
        shard: int = 0,
        text_shard: int = 0,
        voice_shard: int = 0,
        bonus_shard: int = 0,
    ) -> StarGradeData:
        now = datetime.now()
        session.add(
            StarGradeModel(
                user_id=user_id,
                prestige=prestige,
                grade=grade,
                shard=shard,
                text_shard=text_shard,
                voice_shard=voice_shard,
                bonus_shard=bonus_shard,
            )
        )
        await session.flush()
        return StarGradeData(user_id, prestige, grade, shard, text_shard, voice_shard, bonus_shard, now, now)

    async def _write_state(self, data: StarGradeData) -> None:
        async with self.db.session() as session:
            await self._write_state_lock(session, data)
            await session.commit()

    async def _write_state_lock(self, session: AsyncSession, data: StarGradeData) -> None:
        model = await session.get(StarGradeModel, data.user_id)
        if model is None:
            return
        model.prestige = data.prestige
        model.grade = data.grade
        model.shard = data.shard
        model.text_shard = data.text_shard
        model.voice_shard = data.voice_shard
        model.bonus_shard = data.bonus_shard

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
        self, session: AsyncSession, star_grade_data: StarGradeData, add_shard: int
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
        await self._write_state_lock(session, updated)
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
        self, session: AsyncSession, star_grade_data: StarGradeData, add_shard: int
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
        await self._write_state_lock(session, updated)
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
        self, session: AsyncSession, star_grade_data: StarGradeData, add_shard: int
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
        await self._write_state_lock(session, updated)
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
        async with self.db.session() as session:
            model = await session.get(StarGradeModel, user_id)
            if model is not None:
                await session.delete(model)
                await session.commit()
