from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select

from app.database.models.leveling_hotness import LevelingHotnessEventModel
from app.database.table_utils import model_table

HOTNESS_WINDOW = timedelta(hours=24)
DEFAULT_HOTNESS_RANKING_LIMIT = 3


@dataclass(frozen=True, slots=True)
class LevelingHotnessRankingData:
    user_id: int
    hotness: int


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


class LevelingHotness:
    def __init__(self, db: Any) -> None:
        self.db = db

    async def create_table(self) -> None:
        async with self.db.engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: model_table(LevelingHotnessEventModel).create(
                    sync_conn,
                    checkfirst=True,
                )
            )

    async def drop_table(self) -> None:
        async with self.db.engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: model_table(LevelingHotnessEventModel).drop(
                    sync_conn,
                    checkfirst=True,
                )
            )

    async def record_gain(
        self,
        user_id: int,
        amount: int,
        *,
        earned_at: datetime | None = None,
    ) -> None:
        if user_id <= 0:
            raise ValueError("user_id must be positive")
        if amount <= 0:
            raise ValueError("amount must be positive")

        async with self.db.session() as session:
            session.add(
                LevelingHotnessEventModel(
                    user_id=user_id,
                    amount=amount,
                    earned_at=as_utc_naive(earned_at) if earned_at else utc_now_naive(),
                )
            )
            await session.commit()

    async def delete_expired(self, *, now: datetime | None = None) -> int:
        cutoff = (as_utc_naive(now) if now else utc_now_naive()) - HOTNESS_WINDOW
        async with self.db.session() as session:
            result = await session.execute(
                delete(LevelingHotnessEventModel).where(
                    LevelingHotnessEventModel.earned_at < cutoff
                )
            )
            await session.commit()
            return int(result.rowcount or 0)

    async def get_top_hotness(
        self,
        *,
        limit: int = DEFAULT_HOTNESS_RANKING_LIMIT,
        now: datetime | None = None,
    ) -> list[LevelingHotnessRankingData]:
        if limit <= 0:
            return []

        cutoff = (as_utc_naive(now) if now else utc_now_naive()) - HOTNESS_WINDOW
        hotness = func.sum(LevelingHotnessEventModel.amount).label("hotness")
        stmt = (
            select(LevelingHotnessEventModel.user_id, hotness)
            .where(LevelingHotnessEventModel.earned_at >= cutoff)
            .group_by(LevelingHotnessEventModel.user_id)
            .order_by(hotness.desc(), LevelingHotnessEventModel.user_id.asc())
            .limit(limit)
        )
        async with self.db.session() as session:
            result = await session.execute(stmt)
            return [
                LevelingHotnessRankingData(
                    user_id=row.user_id,
                    hotness=int(row.hotness),
                )
                for row in result.all()
            ]
