from __future__ import annotations

from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.timestamps import TimestampMixin


class UserRoleModel(TimestampMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (PrimaryKeyConstraint("user_id", "role_id"),)

    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True))
    role_id: Mapped[int] = mapped_column(BIGINT(unsigned=True))
