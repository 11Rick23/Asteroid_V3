from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select, update

from app.database.models.starred_messages import StarredMessageModel


@dataclass(slots=True)
class StarredMessageData:
    starred_message_id: int
    starboard_message_id: int
    star_amount: int
    user_id: int
    starred_message_channel_id: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class StarAmountRankingData:
    user_id: int
    star_amount: int


class StarredMessages:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _to_data(model: StarredMessageModel | None) -> StarredMessageData | None:
        if model is None:
            return None
        return StarredMessageData(
            starred_message_id=model.starred_message_id,
            starboard_message_id=model.starboard_message_id,
            star_amount=model.star_amount,
            user_id=model.user_id,
            starred_message_channel_id=model.starred_message_channel_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_starred_message(self, message_id: int) -> StarredMessageData | None:
        async with self.db.session() as session:
            return self._to_data(await session.get(StarredMessageModel, message_id))

    async def get_all_starred_messages(self) -> list[StarredMessageData]:
        async with self.db.session() as session:
            stmt = select(StarredMessageModel).order_by(
                StarredMessageModel.created_at.asc(),
                StarredMessageModel.starred_message_id.asc(),
            )
            starred_messages = await session.scalars(stmt)
            return [
                data for starred_message in starred_messages if (data := self._to_data(starred_message)) is not None
            ]

    async def get_random_starred_message(self) -> StarredMessageData | None:
        async with self.db.session() as session:
            stmt = select(StarredMessageModel).order_by(func.rand()).limit(1)
            return self._to_data(await session.scalar(stmt))

    async def get_starred_message_ranking(self, limit: int = 10) -> list[StarredMessageData]:
        async with self.db.session() as session:
            stmt = select(StarredMessageModel).order_by(StarredMessageModel.star_amount.desc()).limit(limit)
            starred_messages = await session.scalars(stmt)
            return [
                data for starred_message in starred_messages if (data := self._to_data(starred_message)) is not None
            ]

    async def get_star_amount_ranking(self, limit: int = 10) -> list[StarAmountRankingData]:
        async with self.db.session() as session:
            total_star_amount = func.sum(StarredMessageModel.star_amount).label("star_amount")
            stmt = (
                select(StarredMessageModel.user_id, total_star_amount)
                .group_by(StarredMessageModel.user_id)
                .order_by(total_star_amount.desc())
                .limit(limit)
            )
            starred_messages = await session.execute(stmt)
            return [
                StarAmountRankingData(user_id=row.user_id, star_amount=row.star_amount) for row in starred_messages
            ]

    async def create_starred_message(
        self,
        message_id: int,
        starboard_message_id: int,
        star_amount: int,
        user_id: int,
        starred_message_channel_id: int,
    ) -> StarredMessageData:
        async with self.db.session() as session:
            model = StarredMessageModel(
                starred_message_id=message_id,
                starboard_message_id=starboard_message_id,
                star_amount=star_amount,
                user_id=user_id,
                starred_message_channel_id=starred_message_channel_id,
            )
            session.add(model)
            await session.flush()
            await session.refresh(model)
            await session.commit()
            data = self._to_data(model)
            if data is None:
                raise RuntimeError(f"starred_messages[{message_id}] の作成に失敗しました。")
            return data

    async def set_star_amount(self, message_id: int, star_amount: int) -> bool:
        async with self.db.session() as session:
            result = await session.execute(
                update(StarredMessageModel)
                .where(StarredMessageModel.starred_message_id == message_id)
                .values(star_amount=star_amount)
            )
            await session.commit()
            return bool(result.rowcount)

    async def set_starboard_message_id(self, message_id: int, starboard_message_id: int) -> bool:
        async with self.db.session() as session:
            result = await session.execute(
                update(StarredMessageModel)
                .where(StarredMessageModel.starred_message_id == message_id)
                .values(starboard_message_id=starboard_message_id)
            )
            await session.commit()
            return bool(result.rowcount)

    async def delete_starred_message(self, message_id: int) -> bool:
        async with self.db.session() as session:
            result = await session.execute(
                delete(StarredMessageModel).where(StarredMessageModel.starred_message_id == message_id)
            )
            await session.commit()
            return bool(result.rowcount)
