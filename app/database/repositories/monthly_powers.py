from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.monthly_powers import MonthlyPowerModel


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

    @staticmethod
    def _to_data(model: MonthlyPowerModel | None) -> MonthlyPowerData | None:
        if model is None:
            return None
        return MonthlyPowerData(
            user_id=model.user_id,
            text_power=model.text_power,
            voice_power=model.voice_power,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_ranking_data(row: Any) -> MonthlyPowerRankingData:
        return MonthlyPowerRankingData(
            user_id=row.user_id,
            text_power=row.text_power,
            voice_power=row.voice_power,
            created_at=row.created_at,
            updated_at=row.updated_at,
            ranking=row.ranking,
        )

    @staticmethod
    def _ranking_subquery():
        total_power = MonthlyPowerModel.text_power + MonthlyPowerModel.voice_power
        ranking = func.rank().over(order_by=total_power.desc())
        return select(
            MonthlyPowerModel.user_id.label("user_id"),
            MonthlyPowerModel.text_power.label("text_power"),
            MonthlyPowerModel.voice_power.label("voice_power"),
            MonthlyPowerModel.created_at.label("created_at"),
            MonthlyPowerModel.updated_at.label("updated_at"),
            ranking.label("ranking"),
        ).subquery()

    async def create_table(self) -> None:
        async with self.db.engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: MonthlyPowerModel.__table__.create(sync_conn, checkfirst=True))

    async def drop_table(self) -> None:
        async with self.db.engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: MonthlyPowerModel.__table__.drop(sync_conn, checkfirst=True))

    async def truncate_table(self) -> None:
        async with self.db.session() as session:
            await session.execute(delete(MonthlyPowerModel))
            await session.commit()

    async def get_monthly_power(self, user_id: int) -> MonthlyPowerData | None:
        async with self.db.session() as session:
            return self._to_data(await session.get(MonthlyPowerModel, user_id))

    async def get_monthly_power_lock(self, session: AsyncSession, user_id: int) -> MonthlyPowerData | None:
        stmt = select(MonthlyPowerModel).where(MonthlyPowerModel.user_id == user_id).with_for_update()
        return self._to_data(await session.scalar(stmt))

    async def get_monthly_power_ranking(
        self, show_user_id: int | None = None, limit: int | None = None
    ) -> list[MonthlyPowerRankingData] | MonthlyPowerRankingData | None:
        ranking_subquery = self._ranking_subquery()

        async with self.db.session() as session:
            if show_user_id is not None:
                stmt = select(ranking_subquery).where(ranking_subquery.c.user_id == show_user_id)
                result = await session.execute(stmt)
                row = result.one_or_none()
                return self._to_ranking_data(row) if row is not None else None

            stmt = select(ranking_subquery).order_by(
                (ranking_subquery.c.text_power + ranking_subquery.c.voice_power).desc()
            )
            if limit is not None and limit > 0:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            return [self._to_ranking_data(row) for row in result.all()]

    async def create_monthly_power(self, user_id: int, text_power: int = 0, voice_power: int = 0) -> MonthlyPowerData:
        async with self.db.session() as session:
            data = await self.create_monthly_power_lock(session, user_id, text_power, voice_power)
            await session.commit()
            return data

    async def create_monthly_power_lock(
        self, session: AsyncSession, user_id: int, text_power: int = 0, voice_power: int = 0
    ) -> MonthlyPowerData:
        now = datetime.now()
        session.add(MonthlyPowerModel(user_id=user_id, text_power=text_power, voice_power=voice_power))
        await session.flush()
        return MonthlyPowerData(user_id, text_power, voice_power, now, now)

    async def add_text_power(self, monthly_power_data: MonthlyPowerData, add_text_power: int) -> MonthlyPowerData:
        async with self.db.session() as session:
            updated = await self.add_text_power_lock(session, monthly_power_data, add_text_power)
            await session.commit()
            return updated

    async def add_text_power_lock(
        self, session: AsyncSession, monthly_power_data: MonthlyPowerData, add_text_power: int
    ) -> MonthlyPowerData:
        model = await session.get(MonthlyPowerModel, monthly_power_data.user_id)
        if model is None:
            return monthly_power_data
        model.text_power += add_text_power
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
        async with self.db.session() as session:
            model = await session.get(MonthlyPowerModel, monthly_power_data.user_id)
            if model is None:
                return monthly_power_data
            model.text_power -= remove_text_power
            await session.commit()
        return MonthlyPowerData(
            monthly_power_data.user_id,
            monthly_power_data.text_power - remove_text_power,
            monthly_power_data.voice_power,
            monthly_power_data.created_at,
            datetime.now(),
        )

    async def add_voice_power(self, monthly_power_data: MonthlyPowerData, add_voice_power: int) -> MonthlyPowerData:
        async with self.db.session() as session:
            updated = await self.add_voice_power_lock(session, monthly_power_data, add_voice_power)
            await session.commit()
            return updated

    async def add_voice_power_lock(
        self, session: AsyncSession, monthly_power_data: MonthlyPowerData, add_voice_power: int
    ) -> MonthlyPowerData:
        model = await session.get(MonthlyPowerModel, monthly_power_data.user_id)
        if model is None:
            return monthly_power_data
        model.voice_power += add_voice_power
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
        async with self.db.session() as session:
            model = await session.get(MonthlyPowerModel, monthly_power_data.user_id)
            if model is None:
                return monthly_power_data
            model.voice_power -= remove_voice_power
            await session.commit()
        return MonthlyPowerData(
            monthly_power_data.user_id,
            monthly_power_data.text_power,
            monthly_power_data.voice_power - remove_voice_power,
            monthly_power_data.created_at,
            datetime.now(),
        )

    async def delete_monthly_power(self, user_id: int) -> None:
        async with self.db.session() as session:
            model = await session.get(MonthlyPowerModel, user_id)
            if model is not None:
                await session.delete(model)
                await session.commit()
