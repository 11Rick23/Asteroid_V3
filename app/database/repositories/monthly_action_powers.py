from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.monthly_action_powers import MonthlyActionPowerModel


@dataclass(slots=True)
class MonthlyActionPowerData:
    user_id: int
    action_power: int
    created_at: datetime
    updated_at: datetime


class MonthlyActionPowers:
    def __init__(self, db):
        self.db = db

    async def _get_or_create_monthly_action_power_model_in_session(
        self, session: AsyncSession, user_id: int
    ) -> MonthlyActionPowerModel:
        stmt = select(MonthlyActionPowerModel).where(MonthlyActionPowerModel.user_id == user_id)
        model = await session.scalar(stmt)
        if model is not None:
            return model

        create_if_missing_stmt = mysql_insert(MonthlyActionPowerModel).values(user_id=user_id, action_power=0)
        await session.execute(
            create_if_missing_stmt.on_duplicate_key_update(
                action_power=MonthlyActionPowerModel.action_power,
            )
        )

        model = await session.scalar(stmt)
        if model is None:
            raise RuntimeError(f"monthly_action_powers[{user_id}] の取得に失敗しました。")
        return model

    @staticmethod
    def _to_data(model: MonthlyActionPowerModel | None) -> MonthlyActionPowerData | None:
        if model is None:
            return None
        return MonthlyActionPowerData(
            user_id=model.user_id,
            action_power=model.action_power,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def reset_monthly_action_powers(self) -> None:
        async with self.db.session() as session:
            await session.execute(delete(MonthlyActionPowerModel))
            await session.commit()

    async def sum_action_power(self) -> int:
        async with self.db.session() as session:
            stmt = select(func.coalesce(func.sum(MonthlyActionPowerModel.action_power), 0))
            return int(await session.scalar(stmt) or 0)

    async def get_monthly_action_power(self, user_id: int) -> MonthlyActionPowerData | None:
        async with self.db.session() as session:
            return self._to_data(await session.get(MonthlyActionPowerModel, user_id))

    async def get_monthly_action_power_in_session(
        self, session: AsyncSession, user_id: int
    ) -> MonthlyActionPowerData | None:
        stmt = select(MonthlyActionPowerModel).where(MonthlyActionPowerModel.user_id == user_id)
        return self._to_data(await session.scalar(stmt))

    async def create_monthly_action_power(self, user_id: int, action_power: int = 0) -> MonthlyActionPowerData:
        async with self.db.session() as session:
            data = await self.create_monthly_action_power_in_session(session, user_id, action_power)
            await session.commit()
            return data

    async def create_monthly_action_power_in_session(
        self, session: AsyncSession, user_id: int, action_power: int = 0
    ) -> MonthlyActionPowerData:
        model = MonthlyActionPowerModel(user_id=user_id, action_power=action_power)
        session.add(model)
        await session.flush()
        await session.refresh(model)
        data = self._to_data(model)
        if data is None:
            raise RuntimeError(f"monthly_action_powers[{user_id}] の作成に失敗しました。")
        return data

    async def add_action_power(
        self, monthly_action_power_data: MonthlyActionPowerData, add_action_power: int
    ) -> MonthlyActionPowerData:
        async with self.db.session() as session:
            updated = await self.add_action_power_in_session(session, monthly_action_power_data, add_action_power)
            await session.commit()
            return updated

    async def add_action_power_in_session(
        self,
        session: AsyncSession,
        monthly_action_power_data: MonthlyActionPowerData,
        add_action_power: int,
    ) -> MonthlyActionPowerData:
        model = await self._get_or_create_monthly_action_power_model_in_session(
            session, monthly_action_power_data.user_id
        )
        model.action_power += add_action_power
        await session.flush()
        await session.refresh(model)
        data = self._to_data(model)
        if data is None:
            raise RuntimeError(f"monthly_action_powers[{monthly_action_power_data.user_id}] の更新に失敗しました。")
        return data

    async def remove_action_power_in_session(
        self,
        session: AsyncSession,
        monthly_action_power_data: MonthlyActionPowerData,
        remove_action_power: int,
    ) -> MonthlyActionPowerData:
        remove_action_power = min(remove_action_power, monthly_action_power_data.action_power)
        model = await session.get(MonthlyActionPowerModel, monthly_action_power_data.user_id)
        if model is None:
            return monthly_action_power_data
        model.action_power -= remove_action_power
        await session.flush()
        await session.refresh(model)
        data = self._to_data(model)
        return data if data is not None else monthly_action_power_data

    async def remove_action_power(
        self, monthly_action_power_data: MonthlyActionPowerData, remove_action_power: int
    ) -> MonthlyActionPowerData:
        async with self.db.session() as session:
            updated = await self.remove_action_power_in_session(
                session,
                monthly_action_power_data,
                remove_action_power,
            )
            await session.commit()
            return updated

    async def delete_monthly_action_power(self, user_id: int) -> None:
        async with self.db.session() as session:
            model = await session.get(MonthlyActionPowerModel, user_id)
            if model is not None:
                await session.delete(model)
                await session.commit()
