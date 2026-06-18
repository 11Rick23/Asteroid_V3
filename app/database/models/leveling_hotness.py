from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, func
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class LevelingHotnessEventModel(Base):
    __tablename__ = "leveling_hotness_events"
    __table_args__ = (Index("ix_leveling_hotness_events_earned_at_user_id", "earned_at", "user_id"),)

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    amount: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False)
    earned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
