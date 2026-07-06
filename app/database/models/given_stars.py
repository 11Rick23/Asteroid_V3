from __future__ import annotations

from sqlalchemy import Index, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.timestamps import TimestampMixin


class GivenStarModel(TimestampMixin, Base):
    __tablename__ = "given_stars"
    __table_args__ = (Index("idx_given_stars_given_star_amount", "given_star_amount"),)

    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    given_star_amount: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0, server_default=text("0"))
