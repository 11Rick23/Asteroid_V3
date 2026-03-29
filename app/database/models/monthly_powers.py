from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class MonthlyPowerModel(Base):
    __tablename__ = "monthly_powers"

    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    text_power: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0)
    voice_power: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
