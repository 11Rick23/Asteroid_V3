from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.timestamps import TimestampMixin


class XPBoostModel(TimestampMixin, Base):
    __tablename__ = "xp_boosts"
    __table_args__ = (Index("idx_xp_boosts_boost_end_time", "boost_end_time"),)

    role_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    boost_amount: Mapped[int] = mapped_column(INTEGER(unsigned=True))
    boost_end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
