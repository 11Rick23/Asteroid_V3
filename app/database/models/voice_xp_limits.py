from __future__ import annotations

from sqlalchemy import Boolean, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.timestamps import TimestampMixin


class VoiceXPLimitModel(TimestampMixin, Base):
    __tablename__ = "voice_xp_limits"

    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    voice_shard: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0, server_default=text("0"))
    bonus_shard: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0, server_default=text("0"))
    voice_power: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0, server_default=text("0"))
    half_notify: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
    full_notify: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))
