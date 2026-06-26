from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, overload

from sqlalchemy import delete, func, select, union
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.monthly_action_powers import MonthlyActionPowerModel
from app.database.models.monthly_powers import MonthlyPowerModel


@dataclass(slots=True)
class MonthlyPowerData:
    user_id: int
    text_power: int
    voice_power: int
    action_power: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class MonthlyPowerRankingData(MonthlyPowerData):
    ranking: int


class MonthlyPowers:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _to_data(row: Any | None) -> MonthlyPowerData | None:
        if row is None:
            return None
        return MonthlyPowerData(
            user_id=row.user_id,
            text_power=row.text_power,
            voice_power=row.voice_power,
            action_power=getattr(row, "action_power", 0),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_ranking_data(row: Any) -> MonthlyPowerRankingData:
        return MonthlyPowerRankingData(
            user_id=row.user_id,
            text_power=row.text_power,
            voice_power=row.voice_power,
            action_power=row.action_power,
            created_at=row.created_at,
            updated_at=row.updated_at,
            ranking=row.ranking,
        )

    @staticmethod
    def _aggregated_subquery(*, include_ranking: bool = True):
        user_ids = union(
            select(MonthlyPowerModel.user_id.label("user_id")),
            select(MonthlyActionPowerModel.user_id.label("user_id")),
        ).subquery()
        text_power = func.coalesce(MonthlyPowerModel.text_power, 0)
        voice_power = func.coalesce(MonthlyPowerModel.voice_power, 0)
        action_power = func.coalesce(MonthlyActionPowerModel.action_power, 0)
        columns = [
            user_ids.c.user_id.label("user_id"),
            text_power.label("text_power"),
            voice_power.label("voice_power"),
            action_power.label("action_power"),
            func.coalesce(MonthlyPowerModel.created_at, MonthlyActionPowerModel.created_at).label("created_at"),
            func.coalesce(MonthlyPowerModel.updated_at, MonthlyActionPowerModel.updated_at).label("updated_at"),
        ]
        if include_ranking:
            total_power = text_power + voice_power + action_power
            columns.append(func.rank().over(order_by=total_power.desc()).label("ranking"))
        return (
            select(*columns)
            .select_from(user_ids)
            .outerjoin(MonthlyPowerModel, MonthlyPowerModel.user_id == user_ids.c.user_id)
            .outerjoin(MonthlyActionPowerModel, MonthlyActionPowerModel.user_id == user_ids.c.user_id)
            .subquery()
        )

    async def _get_or_create_monthly_power_model_in_session(
        self, session: AsyncSession, user_id: int
    ) -> MonthlyPowerModel:
        stmt = select(MonthlyPowerModel).where(MonthlyPowerModel.user_id == user_id)
        model = await session.scalar(stmt)
        if model is not None:
            return model

        # MySQL upsert avoids a PK race when two sessions try to create the first monthly_power row.
        create_if_missing_stmt = mysql_insert(MonthlyPowerModel).values(user_id=user_id, text_power=0, voice_power=0)
        await session.execute(
            create_if_missing_stmt.on_duplicate_key_update(
                text_power=MonthlyPowerModel.text_power,
                voice_power=MonthlyPowerModel.voice_power,
            )
        )

        model = await session.scalar(stmt)
        if model is None:
            raise RuntimeError(f"monthly_powers[{user_id}] の取得に失敗しました。")
        return model

    async def reset_monthly_powers(self) -> None:
        async with self.db.session() as session:
            await self.reset_monthly_powers_in_session(session)
            await session.commit()

    async def reset_monthly_powers_in_session(self, session: AsyncSession) -> None:
        await session.execute(delete(MonthlyPowerModel))

    async def get_monthly_power(self, user_id: int) -> MonthlyPowerData | None:
        async with self.db.session() as session:
            aggregated_subquery = self._aggregated_subquery(include_ranking=False)
            stmt = select(aggregated_subquery).where(aggregated_subquery.c.user_id == user_id)
            result = await session.execute(stmt)
            return self._to_data(result.one_or_none())

    async def get_monthly_power_in_session(self, session: AsyncSession, user_id: int) -> MonthlyPowerData | None:
        stmt = select(MonthlyPowerModel).where(MonthlyPowerModel.user_id == user_id)
        return self._to_data(await session.scalar(stmt))

    @overload
    async def get_monthly_power_ranking(
        self, show_user_id: int, limit: int | None = None
    ) -> MonthlyPowerRankingData | None: ...

    @overload
    async def get_monthly_power_ranking(
        self, show_user_id: None = None, limit: int | None = None
    ) -> list[MonthlyPowerRankingData]: ...

    async def get_monthly_power_ranking(
        self, show_user_id: int | None = None, limit: int | None = None
    ) -> list[MonthlyPowerRankingData] | MonthlyPowerRankingData | None:
        ranking_subquery = self._aggregated_subquery()

        async with self.db.session() as session:
            if show_user_id is not None:
                stmt = select(ranking_subquery).where(ranking_subquery.c.user_id == show_user_id)
                result = await session.execute(stmt)
                row = result.one_or_none()
                return self._to_ranking_data(row) if row is not None else None

            total_power = (
                ranking_subquery.c.text_power + ranking_subquery.c.voice_power + ranking_subquery.c.action_power
            )
            stmt = select(ranking_subquery).order_by(
                total_power.desc(),
                ranking_subquery.c.user_id.asc(),
            )
            if limit is not None and limit > 0:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            return [self._to_ranking_data(row) for row in result.all()]

    async def create_monthly_power(self, user_id: int, text_power: int = 0, voice_power: int = 0) -> MonthlyPowerData:
        async with self.db.session() as session:
            data = await self.create_monthly_power_in_session(session, user_id, text_power, voice_power)
            await session.commit()
            return data

    async def create_monthly_power_in_session(
        self, session: AsyncSession, user_id: int, text_power: int = 0, voice_power: int = 0
    ) -> MonthlyPowerData:
        model = MonthlyPowerModel(user_id=user_id, text_power=text_power, voice_power=voice_power)
        session.add(model)
        await session.flush()
        await session.refresh(model)
        data = self._to_data(model)
        if data is None:
            raise RuntimeError(f"monthly_powers[{user_id}] の作成に失敗しました。")
        return data

    async def add_text_power(self, monthly_power_data: MonthlyPowerData, add_text_power: int) -> MonthlyPowerData:
        async with self.db.session() as session:
            updated = await self.add_text_power_in_session(session, monthly_power_data, add_text_power)
            await session.commit()
            return updated

    async def add_text_power_in_session(
        self, session: AsyncSession, monthly_power_data: MonthlyPowerData, add_text_power: int
    ) -> MonthlyPowerData:
        model = await self._get_or_create_monthly_power_model_in_session(session, monthly_power_data.user_id)
        model.text_power += add_text_power
        await session.flush()
        await session.refresh(model)
        return MonthlyPowerData(
            model.user_id,
            model.text_power,
            model.voice_power,
            monthly_power_data.action_power,
            model.created_at,
            model.updated_at,
        )

    async def remove_text_power(
        self, monthly_power_data: MonthlyPowerData, remove_text_power: int
    ) -> MonthlyPowerData:
        async with self.db.session() as session:
            updated = await self.remove_text_power_in_session(session, monthly_power_data, remove_text_power)
            await session.commit()
            return updated

    async def remove_text_power_in_session(
        self, session: AsyncSession, monthly_power_data: MonthlyPowerData, remove_text_power: int
    ) -> MonthlyPowerData:
        model = await session.get(MonthlyPowerModel, monthly_power_data.user_id)
        if model is None:
            return monthly_power_data
        remove_text_power = min(remove_text_power, model.text_power)
        model.text_power -= remove_text_power
        await session.flush()
        await session.refresh(model)
        return MonthlyPowerData(
            model.user_id,
            model.text_power,
            model.voice_power,
            monthly_power_data.action_power,
            model.created_at,
            model.updated_at,
        )

    async def add_voice_power(self, monthly_power_data: MonthlyPowerData, add_voice_power: int) -> MonthlyPowerData:
        async with self.db.session() as session:
            updated = await self.add_voice_power_in_session(session, monthly_power_data, add_voice_power)
            await session.commit()
            return updated

    async def add_voice_power_in_session(
        self, session: AsyncSession, monthly_power_data: MonthlyPowerData, add_voice_power: int
    ) -> MonthlyPowerData:
        model = await self._get_or_create_monthly_power_model_in_session(session, monthly_power_data.user_id)
        model.voice_power += add_voice_power
        await session.flush()
        await session.refresh(model)
        return MonthlyPowerData(
            model.user_id,
            model.text_power,
            model.voice_power,
            monthly_power_data.action_power,
            model.created_at,
            model.updated_at,
        )

    async def remove_voice_power(
        self, monthly_power_data: MonthlyPowerData, remove_voice_power: int
    ) -> MonthlyPowerData:
        async with self.db.session() as session:
            updated = await self.remove_voice_power_in_session(session, monthly_power_data, remove_voice_power)
            await session.commit()
            return updated

    async def remove_voice_power_in_session(
        self, session: AsyncSession, monthly_power_data: MonthlyPowerData, remove_voice_power: int
    ) -> MonthlyPowerData:
        model = await session.get(MonthlyPowerModel, monthly_power_data.user_id)
        if model is None:
            return monthly_power_data
        remove_voice_power = min(remove_voice_power, model.voice_power)
        model.voice_power -= remove_voice_power
        await session.flush()
        await session.refresh(model)
        return MonthlyPowerData(
            model.user_id,
            model.text_power,
            model.voice_power,
            monthly_power_data.action_power,
            model.created_at,
            model.updated_at,
        )

    async def delete_monthly_power(self, user_id: int) -> None:
        async with self.db.session() as session:
            model = await session.get(MonthlyPowerModel, user_id)
            if model is not None:
                await session.delete(model)
                await session.commit()
