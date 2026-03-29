from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select

from app.database.models.xp_boosts import XPBoostModel


@dataclass
class XPBoostData:
    role_id: int
    name: str
    boost_amount: int
    boost_end_time: datetime | None
    created_at: datetime
    updated_at: datetime


class XPBoosts:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _to_data(model: XPBoostModel | None) -> XPBoostData | None:
        if model is None:
            return None
        return XPBoostData(
            role_id=model.role_id,
            name=model.name,
            boost_amount=model.boost_amount,
            boost_end_time=model.boost_end_time,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def create_table(self) -> None:
        async with self.db.engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: XPBoostModel.__table__.create(sync_conn, checkfirst=True))

    async def drop_table(self) -> None:
        async with self.db.engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: XPBoostModel.__table__.drop(sync_conn, checkfirst=True))

    async def get_xp_boosts(self) -> list[XPBoostData]:
        async with self.db.session() as session:
            result = await session.scalars(select(XPBoostModel))
            return [self._to_data(xp_boost) for xp_boost in result if xp_boost is not None]

    async def get_xp_boost(self, role_id: int) -> XPBoostData | None:
        async with self.db.session() as session:
            return self._to_data(await session.get(XPBoostModel, role_id))

    async def create_xp_boost(
        self, role_id: int, name: str, boost_amount: int, boost_end_time: datetime | None
    ) -> None:
        async with self.db.session() as session:
            session.add(
                XPBoostModel(
                    role_id=role_id,
                    name=name,
                    boost_amount=boost_amount,
                    boost_end_time=boost_end_time,
                )
            )
            await session.commit()

    async def delete_xp_boost(self, role_id: int) -> None:
        async with self.db.session() as session:
            model = await session.get(XPBoostModel, role_id)
            if model is not None:
                await session.delete(model)
                await session.commit()

    async def delete_expired_xp_boosts(self) -> None:
        async with self.db.session() as session:
            await session.execute(
                delete(XPBoostModel).where(XPBoostModel.boost_end_time.is_not(None), XPBoostModel.boost_end_time < func.now())
            )
            await session.commit()
