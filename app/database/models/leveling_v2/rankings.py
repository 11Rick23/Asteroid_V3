from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import ID, Amount, LevelingBase, UTCDateTime


class RankingRevision(LevelingBase):
    __tablename__ = "leveling_ranking_revisions"
    __table_args__ = (
        CheckConstraint("source IN ('close','correction')", name="source"),
        CheckConstraint("revision > 0", name="revision"),
        {"mysql_engine": "InnoDB"},
    )

    period_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_periods.period_id", ondelete="RESTRICT"), primary_key=True
    )
    revision: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    source: Mapped[str] = mapped_column(String(16))
    correction_id: Mapped[int | None] = mapped_column(
        ID, ForeignKey("leveling_corrections.correction_id", ondelete="RESTRICT")
    )
    row_count: Mapped[int] = mapped_column(ID)
    checksum: Mapped[str] = mapped_column(String(64))


class SnapshotUserInput(LevelingBase):
    __tablename__ = "leveling_snapshot_user_inputs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["period_id", "revision"],
            ["leveling_ranking_revisions.period_id", "leveling_ranking_revisions.revision"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("unallocated_text >= 0 AND unallocated_voice >= 0 AND action_power >= 0", name="amounts"),
        {"mysql_engine": "InnoDB"},
    )

    period_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    revision: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    user_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_accounts.user_id", ondelete="RESTRICT"), primary_key=True
    )
    unallocated_text: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    unallocated_voice: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    action_power: Mapped[int] = mapped_column(Amount, default=0, server_default="0")


class SnapshotChannelInput(LevelingBase):
    __tablename__ = "leveling_snapshot_channel_inputs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["period_id", "revision"],
            ["leveling_ranking_revisions.period_id", "leveling_ranking_revisions.revision"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("kind IN ('text','voice')", name="kind"),
        CheckConstraint("power > 0", name="power"),
        Index("ix_leveling_snapshot_channel_inputs_user", "period_id", "revision", "user_id", "kind"),
        {"mysql_engine": "InnoDB"},
    )

    period_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    revision: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    channel_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_channels.channel_id", ondelete="RESTRICT"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_accounts.user_id", ondelete="RESTRICT"), primary_key=True
    )
    power: Mapped[int] = mapped_column(Amount, default=0, server_default="0")


class RankingRow(LevelingBase):
    __tablename__ = "leveling_ranking_rows"
    __table_args__ = (
        ForeignKeyConstraint(
            ["period_id", "revision"],
            ["leveling_ranking_revisions.period_id", "leveling_ranking_revisions.revision"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("score > 0 AND `rank` > 0", name="score_rank"),
        CheckConstraint(
            "(scope = 'user' AND metric IN ('total','text','voice','action') AND channel_key = 0) "
            "OR (scope = 'channel' AND metric IN ('text','voice') AND channel_key = 0) OR (scope = "
            "'channel_user' AND metric IN ('text','voice') AND channel_key > 0)",
            name="scope",
        ),
        Index(
            "ix_leveling_ranking_rows_page",
            "period_id",
            "revision",
            "scope",
            "metric",
            "channel_key",
            "rank",
            "subject_id",
        ),
        {"mysql_engine": "InnoDB"},
    )

    period_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    revision: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    scope: Mapped[str] = mapped_column(String(16), primary_key=True)
    metric: Mapped[str] = mapped_column(String(8), primary_key=True)
    channel_key: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    subject_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    score: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    rank: Mapped[int] = mapped_column(ID)
