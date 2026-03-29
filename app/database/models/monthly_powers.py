from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MonthlyPowerModel(Base):
    __tablename__ = "monthly_powers"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    text_power: Mapped[int] = mapped_column(Integer, default=0)
    voice_power: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
