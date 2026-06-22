from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, func
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class UserBirthdayModel(Base):
    __tablename__ = "user_birthdays"
    __table_args__ = (
        Index("idx_user_birthdays_date", "date"),
    )

    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
