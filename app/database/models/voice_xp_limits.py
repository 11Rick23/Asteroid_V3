from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class VoiceXPLimitModel(Base):
    __tablename__ = "voice_xp_limits"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    voice_shard: Mapped[int] = mapped_column(Integer, default=0)
    bonus_shard: Mapped[int] = mapped_column(Integer, default=0)
    voice_power: Mapped[int] = mapped_column(Integer, default=0)
    half_notify: Mapped[bool] = mapped_column(Boolean, default=False)
    full_notify: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
