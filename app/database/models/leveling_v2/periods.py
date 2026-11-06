from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import ID, Amount, LevelingBase, UTCDateTime


class PeriodRow(LevelingBase):
    __tablename__ = "leveling_periods"
    __table_args__ = (
        UniqueConstraint("kind", "start_at"),
        CheckConstraint("kind IN ('day','week','month')", name="kind"),
        CheckConstraint("status IN ('OPEN','FINALIZED')", name="status"),
        CheckConstraint("start_at < end_at", name="interval"),
        CheckConstraint(
            "(status = 'OPEN' AND current_revision = 0 AND finalized_at IS NULL) OR (status = "
            "'FINALIZED' AND current_revision > 0 AND finalized_at IS NOT NULL)",
            name="publication",
        ),
        Index("ix_leveling_periods_close", "status", "end_at", "period_id"),
        {"mysql_engine": "InnoDB"},
    )

    period_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(8))
    start_at: Mapped[datetime] = mapped_column(UTCDateTime)
    end_at: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", server_default="OPEN")
    finalized_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    current_revision: Mapped[int] = mapped_column(ID, default=0, server_default="0")
    coverage_start_at: Mapped[datetime] = mapped_column(UTCDateTime)


class PeriodUser(LevelingBase):
    __tablename__ = "leveling_period_users"
    __table_args__ = (
        CheckConstraint(
            "text_power >= 0 AND voice_power >= 0 AND action_power >= 0 AND unallocated_text >= 0 "
            "AND unallocated_voice >= 0",
            name="balances",
        ),
        CheckConstraint("unallocated_text <= text_power AND unallocated_voice <= voice_power", name="unallocated"),
        CheckConstraint("total_power = text_power + voice_power + action_power", name="total"),
        {"mysql_engine": "InnoDB"},
    )

    period_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_periods.period_id", ondelete="RESTRICT"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_accounts.user_id", ondelete="RESTRICT"), primary_key=True
    )
    text_power: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    voice_power: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    action_power: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    unallocated_text: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    unallocated_voice: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    total_power: Mapped[int] = mapped_column(Amount, default=0, server_default="0")


Index("ix_leveling_period_users_total", PeriodUser.period_id, PeriodUser.total_power.desc(), PeriodUser.user_id)

Index("ix_leveling_period_users_text", PeriodUser.period_id, PeriodUser.text_power.desc(), PeriodUser.user_id)

Index("ix_leveling_period_users_voice", PeriodUser.period_id, PeriodUser.voice_power.desc(), PeriodUser.user_id)

Index("ix_leveling_period_users_action", PeriodUser.period_id, PeriodUser.action_power.desc(), PeriodUser.user_id)


class PeriodChannelUser(LevelingBase):
    __tablename__ = "leveling_period_channel_users"
    __table_args__ = (
        CheckConstraint("kind IN ('text','voice')", name="kind"),
        CheckConstraint("power >= 0", name="power"),
        {"mysql_engine": "InnoDB"},
    )

    period_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_periods.period_id", ondelete="RESTRICT"), primary_key=True
    )
    channel_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_channels.channel_id", ondelete="RESTRICT"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_accounts.user_id", ondelete="RESTRICT"), primary_key=True
    )
    power: Mapped[int] = mapped_column(Amount, default=0, server_default="0")


Index(
    "ix_leveling_period_channel_users_rank",
    PeriodChannelUser.period_id,
    PeriodChannelUser.kind,
    PeriodChannelUser.channel_id,
    PeriodChannelUser.power.desc(),
    PeriodChannelUser.user_id,
)


class PeriodChannel(LevelingBase):
    __tablename__ = "leveling_period_channels"
    __table_args__ = (
        CheckConstraint("kind IN ('text','voice')", name="kind"),
        CheckConstraint("power >= 0", name="power"),
        {"mysql_engine": "InnoDB"},
    )

    period_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_periods.period_id", ondelete="RESTRICT"), primary_key=True
    )
    channel_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_channels.channel_id", ondelete="RESTRICT"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(8), primary_key=True)
    power: Mapped[int] = mapped_column(Amount, default=0, server_default="0")


Index(
    "ix_leveling_period_channels_rank",
    PeriodChannel.period_id,
    PeriodChannel.kind,
    PeriodChannel.power.desc(),
    PeriodChannel.channel_id,
)
