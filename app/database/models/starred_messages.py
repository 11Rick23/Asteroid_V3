from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class StarredMessageModel(Base):
    __tablename__ = "starred_messages"

    starred_message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    starboard_message_id: Mapped[int] = mapped_column(BigInteger)
    star_amount: Mapped[int] = mapped_column(Integer, default=0)
    user_id: Mapped[int] = mapped_column(BigInteger)
    starred_message_channel_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
