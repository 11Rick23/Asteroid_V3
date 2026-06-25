from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.given_stars import GivenStarModel


@dataclass(slots=True)
class GivenStarData:
    user_id: int
    given_star_amount: int
    created_at: datetime
    updated_at: datetime


class GivenStars:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _to_data(model: GivenStarModel | None) -> GivenStarData | None:
        if model is None:
            return None
        return GivenStarData(
            user_id=model.user_id,
            given_star_amount=model.given_star_amount,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_given_star(self, user_id: int) -> GivenStarData | None:
        async with self.db.session() as session:
            return self._to_data(await session.get(GivenStarModel, user_id))

    async def get_given_star_ranking(self, limit: int = 10) -> list[GivenStarData]:
        async with self.db.session() as session:
            stmt = select(GivenStarModel).order_by(GivenStarModel.given_star_amount.desc()).limit(limit)
            given_stars = await session.scalars(stmt)
            return [data for given_star in given_stars if (data := self._to_data(given_star)) is not None]

    async def create_given_star(self, user_id: int, given_star_amount: int = 1) -> None:
        async with self.db.session() as session:
            await self._add_given_star_in_session(session, user_id, given_star_amount)
            await session.commit()

    async def add_given_star(self, user_id: int, given_star_amount: int = 1) -> None:
        async with self.db.session() as session:
            await self._add_given_star_in_session(session, user_id, given_star_amount)
            await session.commit()

    async def remove_given_star(self, user_id: int, given_star_amount: int = 1) -> None:
        async with self.db.session() as session:
            stmt = (
                update(GivenStarModel)
                .where(GivenStarModel.user_id == user_id)
                .values(
                    given_star_amount=func.greatest(GivenStarModel.given_star_amount - given_star_amount, 0),
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def _add_given_star_in_session(
        self, session: AsyncSession, user_id: int, given_star_amount: int
    ) -> None:
        stmt = mysql_insert(GivenStarModel).values(user_id=user_id, given_star_amount=given_star_amount)
        await session.execute(
            stmt.on_duplicate_key_update(
                given_star_amount=GivenStarModel.given_star_amount + given_star_amount,
            )
        )
