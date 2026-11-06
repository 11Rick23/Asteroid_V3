from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import ID, Amount, LevelingBase, UTCDateTime


class Correction(LevelingBase):
    __tablename__ = "leveling_corrections"
    __table_args__ = (
        UniqueConstraint("request_key"),
        {"mysql_engine": "InnoDB"},
    )

    correction_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    request_key: Mapped[str] = mapped_column(String(191))
    actor_id: Mapped[int] = mapped_column(ID)
    reason: Mapped[str] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime)
    approved_at: Mapped[datetime] = mapped_column(UTCDateTime)
    preview_hash: Mapped[str] = mapped_column(String(64))
    reannounce: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(32))


class CorrectionChange(LevelingBase):
    __tablename__ = "leveling_correction_changes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["period_id", "old_revision"],
            ["leveling_ranking_revisions.period_id", "leveling_ranking_revisions.revision"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["period_id", "new_revision"],
            ["leveling_ranking_revisions.period_id", "leveling_ranking_revisions.revision"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("old_score >= 0 AND new_score >= 0", name="scores"),
        {"mysql_engine": "InnoDB"},
    )

    correction_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_corrections.correction_id", ondelete="RESTRICT"), primary_key=True
    )
    change_seq: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    period_id: Mapped[int] = mapped_column(ID, ForeignKey("leveling_periods.period_id", ondelete="RESTRICT"))
    old_revision: Mapped[int] = mapped_column(ID)
    new_revision: Mapped[int] = mapped_column(ID)
    scope: Mapped[str] = mapped_column(String(16))
    metric: Mapped[str] = mapped_column(String(8))
    channel_key: Mapped[int] = mapped_column(ID)
    subject_id: Mapped[int] = mapped_column(ID)
    old_score: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    new_score: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    old_rank: Mapped[int | None] = mapped_column(ID)
    new_rank: Mapped[int | None] = mapped_column(ID)


class CorrectionRoleChoice(LevelingBase):
    __tablename__ = "leveling_correction_role_choices"
    __table_args__ = ({"mysql_engine": "InnoDB"},)

    correction_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_corrections.correction_id", ondelete="RESTRICT"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_accounts.user_id", ondelete="RESTRICT"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    old_qualified: Mapped[bool] = mapped_column(Boolean)
    new_qualified: Mapped[bool] = mapped_column(Boolean)
    decision: Mapped[str] = mapped_column(String(32))
    old_desired: Mapped[bool] = mapped_column(Boolean)
    new_desired: Mapped[bool] = mapped_column(Boolean)
    execution_result: Mapped[str | None] = mapped_column(String(32))
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Operation(LevelingBase):
    __tablename__ = "leveling_operations"
    __table_args__ = ({"mysql_engine": "InnoDB"},)

    operation_key: Mapped[str] = mapped_column(String(191), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[int] = mapped_column(ID)
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    before_values: Mapped[dict[str, object]] = mapped_column(JSON)
    after_values: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class EventOwnershipMove(LevelingBase):
    __tablename__ = "leveling_event_ownership_moves"
    __table_args__ = ({"mysql_engine": "InnoDB"},)

    operation_key: Mapped[str] = mapped_column(
        String(191), ForeignKey("leveling_operations.operation_key", ondelete="RESTRICT"), primary_key=True
    )
    source_user_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_accounts.user_id", ondelete="RESTRICT"), primary_key=True
    )
    target_user_id: Mapped[int] = mapped_column(ID, ForeignKey("leveling_accounts.user_id", ondelete="RESTRICT"))
    cutoff_event_id: Mapped[int] = mapped_column(ID)
    moved_at: Mapped[datetime] = mapped_column(UTCDateTime)
