from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.timestamps import TimestampMixin


class MonthlyActionPowerModel(TimestampMixin, Base):
    __tablename__ = "monthly_action_powers"

    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    action_power: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0, server_default=text("0"))
