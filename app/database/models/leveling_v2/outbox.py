from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import ID, LevelingBase, UTCDateTime


class MonthlyQualification(LevelingBase):
    __tablename__ = "leveling_monthly_qualifications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["month_period_id", "ranking_revision"],
            ["leveling_ranking_revisions.period_id", "leveling_ranking_revisions.revision"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("is_top1 = 0 OR is_top10 = 1", name="top1"),
        {"mysql_engine": "InnoDB"},
    )

    month_period_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_periods.period_id", ondelete="RESTRICT"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_accounts.user_id", ondelete="RESTRICT"), primary_key=True
    )
    ranking_revision: Mapped[int] = mapped_column(ID)
    is_top1: Mapped[bool] = mapped_column(Boolean)
    is_top10: Mapped[bool] = mapped_column(Boolean)
    consecutive_top1: Mapped[int] = mapped_column(ID)


class PermanentAward(LevelingBase):
    __tablename__ = "leveling_permanent_awards"
    __table_args__ = ({"mysql_engine": "InnoDB"},)

    user_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_accounts.user_id", ondelete="RESTRICT"), primary_key=True
    )
    award_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    first_earned_month: Mapped[int] = mapped_column(ID, ForeignKey("leveling_periods.period_id", ondelete="RESTRICT"))
    earned_at: Mapped[datetime] = mapped_column(UTCDateTime)
    desired_granted: Mapped[bool] = mapped_column(Boolean)
    decision_version: Mapped[int] = mapped_column(ID)
    last_correction_id: Mapped[int | None] = mapped_column(
        ID, ForeignKey("leveling_corrections.correction_id", ondelete="RESTRICT")
    )


class RoleDesire(LevelingBase):
    __tablename__ = "leveling_role_desires"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_month", "source_revision"],
            ["leveling_ranking_revisions.period_id", "leveling_ranking_revisions.revision"],
            ondelete="RESTRICT",
        ),
        {"mysql_engine": "InnoDB"},
    )

    user_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_accounts.user_id", ondelete="RESTRICT"), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    desired: Mapped[bool] = mapped_column(Boolean)
    generation: Mapped[int] = mapped_column(ID)
    source_month: Mapped[int | None] = mapped_column(ID)
    source_revision: Mapped[int | None] = mapped_column(ID)
    synced_generation: Mapped[int | None] = mapped_column(ID)


class OutboxJob(LevelingBase):
    __tablename__ = "leveling_outbox"
    __table_args__ = (
        UniqueConstraint("dedupe_key"),
        CheckConstraint(
            "state IN ('pending','leased','retry_wait','completed','unknown','needs_attention')", name="state"
        ),
        Index("ix_leveling_outbox_due", "state", "next_attempt_at", "job_id"),
        Index("ix_leveling_outbox_expiry", "expires_at", "job_id"),
        {"mysql_engine": "InnoDB"},
    )

    job_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    dedupe_key: Mapped[str] = mapped_column(String(191))
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String(32))
    attempt_count: Mapped[int] = mapped_column(ID, default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(UTCDateTime)
    lease_until: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_error_code: Mapped[str | None] = mapped_column(String(64))
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    lease_token: Mapped[str | None] = mapped_column(String(64))
    audit_operation_key: Mapped[str | None] = mapped_column(
        String(191), ForeignKey("leveling_operations.operation_key", ondelete="RESTRICT")
    )


class AnnouncementPart(LevelingBase):
    __tablename__ = "leveling_announcement_parts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["period_id", "revision"],
            ["leveling_ranking_revisions.period_id", "leveling_ranking_revisions.revision"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "state IN ('PREPARED','SENDING','SENT','RETRY_WAIT','UNKNOWN','NEEDS_ATTENTION')", name="state"
        ),
        {"mysql_engine": "InnoDB"},
    )

    period_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    revision: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    part_no: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    channel_id: Mapped[int] = mapped_column(ID)
    message_id: Mapped[int | None] = mapped_column(ID)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    payload_hash: Mapped[str] = mapped_column(String(64))
    marker: Mapped[str] = mapped_column(String(191))
    state: Mapped[str] = mapped_column(String(32))
    attempt_token: Mapped[str | None] = mapped_column(String(64))
    send_started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
