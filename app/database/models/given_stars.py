from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, func
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class GivenStarModel(Base):
    __tablename__ = "given_stars"
    __table_args__ = (Index("idx_given_stars_given_star_amount", "given_star_amount"),)

    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    given_star_amount: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
