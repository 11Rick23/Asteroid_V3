from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class XPBoostModel(Base):
    __tablename__ = "xp_boosts"
    __table_args__ = (Index("idx_xp_boosts_boost_end_time", "boost_end_time"),)

    role_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    boost_amount: Mapped[int] = mapped_column(INTEGER(unsigned=True))
    boost_end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
