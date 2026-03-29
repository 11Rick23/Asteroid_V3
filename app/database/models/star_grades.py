from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class StarGradeModel(Base):
    __tablename__ = "star_grades"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    prestige: Mapped[int] = mapped_column(SmallInteger, default=0)
    grade: Mapped[int] = mapped_column(SmallInteger, default=0)
    shard: Mapped[int] = mapped_column(Integer, default=0)
    text_shard: Mapped[int] = mapped_column(Integer, default=0)
    voice_shard: Mapped[int] = mapped_column(Integer, default=0)
    bonus_shard: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
