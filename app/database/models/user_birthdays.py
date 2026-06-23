from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Index
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.timestamps import TimestampMixin


class UserBirthdayModel(TimestampMixin, Base):
    __tablename__ = "user_birthdays"
    __table_args__ = (
        Index("idx_user_birthdays_date", "date"),
    )

    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    date: Mapped[date] = mapped_column(Date)
