from __future__ import annotations

from sqlalchemy import Index, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.timestamps import TimestampMixin


class StarredMessageModel(TimestampMixin, Base):
    __tablename__ = "starred_messages"
    __table_args__ = (
        Index("idx_starred_messages_star_amount", "star_amount"),
        Index("idx_starred_messages_user_id", "user_id"),
    )

    starred_message_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    starboard_message_id: Mapped[int] = mapped_column(BIGINT(unsigned=True))
    star_amount: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0, server_default=text("0"))
    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True))
    starred_message_channel_id: Mapped[int] = mapped_column(BIGINT(unsigned=True))
