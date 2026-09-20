from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.leveling_state import PowerState, ShardState
from app.database.models.monthly_action_powers import MonthlyActionPowerModel
from app.database.models.monthly_powers import MonthlyPowerModel
from app.database.models.star_grades import StarGradeModel
from app.database.repositories.star_grades import StarGradeData, StarGrades


class LevelingStateRepository:
    def __init__(self, db: Any) -> None:
        self.db = db

    async def set_shards(self, user_id: int, values: ShardState) -> StarGradeData:
        values.validate()
        async with self.db.leveling._user_update(user_id):
            async with self.db.session() as session:
                data = await self.write_shards(session, user_id, values)
                await session.commit()
                return data

    async def set_powers(self, user_id: int, values: PowerState) -> None:
        values.validate()
        async with self.db.leveling._user_update(user_id):
            async with self.db.session() as session:
                await self.write_powers(session, user_id, values)
                await session.commit()

    async def write_shards(self, session: AsyncSession, user_id: int, values: ShardState) -> StarGradeData:
        prestige, grade, shard = values.progression()
        model = await session.get(StarGradeModel, user_id)
        if model is None:
            model = StarGradeModel(user_id=user_id)
            session.add(model)
        model.text_shard, model.voice_shard, model.bonus_shard = values.text, values.voice, values.bonus
        model.prestige, model.grade, model.shard = prestige, grade, shard
        await session.flush()
        await session.refresh(model)
        data = StarGrades._to_data(model)
        assert data is not None
        return data

    async def write_powers(self, session: AsyncSession, user_id: int, values: PowerState) -> None:
        values.validate()
        monthly = await session.get(MonthlyPowerModel, user_id)
        if monthly is None:
            monthly = MonthlyPowerModel(user_id=user_id)
            session.add(monthly)
        action = await session.get(MonthlyActionPowerModel, user_id)
        if action is None:
            action = MonthlyActionPowerModel(user_id=user_id)
            session.add(action)
        monthly.text_power, monthly.voice_power = values.text, values.voice
        action.action_power = values.action
