from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, PrimaryKeyConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class UserRoleModel(Base):
    __tablename__ = "user_roles"
    __table_args__ = (PrimaryKeyConstraint("user_id", "role_id"),)

    user_id: Mapped[int] = mapped_column(BigInteger)
    role_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
