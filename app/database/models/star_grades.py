from __future__ import annotations

from sqlalchemy import Index, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.timestamps import TimestampMixin


class StarGradeModel(TimestampMixin, Base):
    __tablename__ = "star_grades"
    __table_args__ = (Index("idx_star_grades_ranking", "prestige", "grade", "shard"),)

    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    prestige: Mapped[int] = mapped_column(TINYINT(unsigned=True), default=0, server_default=text("0"))
    grade: Mapped[int] = mapped_column(TINYINT(unsigned=True), default=0, server_default=text("0"))
    shard: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0, server_default=text("0"))
    text_shard: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0, server_default=text("0"))
    voice_shard: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0, server_default=text("0"))
    bonus_shard: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0, server_default=text("0"))
