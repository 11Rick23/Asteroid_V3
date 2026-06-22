from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime

from sqlalchemy import select

from app.database.models.user_birthdays import UserBirthdayModel


@dataclass
class UserBirthdayData:
    user_id: int
    date: Date
    created_at: datetime
    updated_at: datetime


class UserBirthdays:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _to_data(model: UserBirthdayModel | None) -> UserBirthdayData | None:
        if model is None:
            return None
        return UserBirthdayData(
            user_id=model.user_id,
            date=model.date,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_user_data(self, user_id: int) -> UserBirthdayData | None:
        async with self.db.session() as session:
            return self._to_data(await session.get(UserBirthdayModel, user_id))

    async def get_user_data_by_date(self, date: Date) -> list[UserBirthdayData]:
        async with self.db.session() as session:
            stmt = select(UserBirthdayModel).where(UserBirthdayModel.date == date)
            raw_data = await session.scalars(stmt)
            return [data for raw in raw_data if (data := self._to_data(raw)) is not None]

    async def get_sorted_all_user_data(self) -> list[UserBirthdayData]:
        async with self.db.session() as session:
            raw_data = await session.scalars(select(UserBirthdayModel))
            data = [birthday for raw in raw_data if (birthday := self._to_data(raw)) is not None]
        return sorted(data, key=lambda x: (x.date.month, x.date.day))

    async def upsert_data(self, user_id: int, date: Date) -> None:
        async with self.db.session() as session:
            model = await session.get(UserBirthdayModel, user_id)
            if model is None:
                session.add(UserBirthdayModel(user_id=user_id, date=date))
            else:
                model.date = date
            await session.commit()

    async def delete_data(self, user_id: int) -> None:
        async with self.db.session() as session:
            model = await session.get(UserBirthdayModel, user_id)
            if model is not None:
                await session.delete(model)
                await session.commit()
