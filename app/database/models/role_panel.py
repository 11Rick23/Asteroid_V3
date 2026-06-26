from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, PrimaryKeyConstraint, String, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.models.timestamps import TimestampMixin


class RolePanelCategoryModel(TimestampMixin, Base):
    __tablename__ = "role_panel_categories"
    __table_args__ = (Index("idx_role_panel_categories_display_order", "display_order"),)

    category_id: Mapped[int] = mapped_column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    display_order: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0, server_default=text("0"))
    requires_boost: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("0"))


class RolePanelRoleModel(TimestampMixin, Base):
    __tablename__ = "role_panel_roles"
    __table_args__ = (
        PrimaryKeyConstraint("category_id", "role_id"),
        Index("idx_role_panel_roles_category_order", "category_id", "display_order", "role_id"),
    )

    category_id: Mapped[int] = mapped_column(
        INTEGER(unsigned=True),
        ForeignKey("role_panel_categories.category_id", ondelete="CASCADE"),
    )
    role_id: Mapped[int] = mapped_column(BIGINT(unsigned=True))
    display_order: Mapped[int] = mapped_column(INTEGER(unsigned=True), default=0, server_default=text("0"))
