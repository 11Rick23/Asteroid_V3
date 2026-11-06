from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import ID, Amount, LevelingBase, UTCDateTime


class Event(LevelingBase):
    __tablename__ = "leveling_events"
    __table_args__ = (
        UniqueConstraint("operation_key"),
        CheckConstraint("kind IN ('text','voice','action','admin','import','claim')", name="kind"),
        CheckConstraint("raw_xp >= 0 AND base_shard >= 0 AND bonus_shard >= 0 AND power >= 0", name="amounts"),
        CheckConstraint(
            "(interval_start IS NULL AND interval_end IS NULL) OR (interval_start IS NOT NULL AND "
            "interval_end IS NOT NULL AND interval_start < interval_end)",
            name="interval",
        ),
        Index("ix_leveling_events_user", "user_id", "occurred_at", "event_id"),
        Index("ix_leveling_events_kind", "kind", "occurred_at", "event_id"),
        Index("ix_leveling_events_time", "occurred_at", "event_id"),
        Index("ix_leveling_events_expiry", "expires_at", "event_id"),
        {"mysql_engine": "InnoDB"},
    )

    event_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    operation_key: Mapped[str] = mapped_column(String(191))
    user_id: Mapped[int] = mapped_column(ID, ForeignKey("leveling_accounts.user_id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(16))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    interval_start: Mapped[datetime | None] = mapped_column(UTCDateTime)
    interval_end: Mapped[datetime | None] = mapped_column(UTCDateTime)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    raw_xp: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    base_shard: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    bonus_shard: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    power: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    source_message_id: Mapped[int | None] = mapped_column(ID)
    source_bot_id: Mapped[int | None] = mapped_column(ID)
    status: Mapped[str] = mapped_column(String(32))
    calculation_version: Mapped[str] = mapped_column(String(64))
    calculation_inputs: Mapped[dict[str, object]] = mapped_column(JSON)


class EventChannel(LevelingBase):
    __tablename__ = "leveling_event_channels"
    __table_args__ = (
        CheckConstraint("duration_us >= 0 AND allocated_power >= 0", name="amounts"),
        Index("ix_leveling_event_channels_channel", "channel_id", "event_id"),
        {"mysql_engine": "InnoDB"},
    )

    event_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_events.event_id", ondelete="CASCADE"), primary_key=True
    )
    channel_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_channels.channel_id", ondelete="RESTRICT"), primary_key=True
    )
    duration_us: Mapped[int] = mapped_column(BigInteger)
    allocated_power: Mapped[int] = mapped_column(Amount, default=0, server_default="0")


class EventPeriod(LevelingBase):
    __tablename__ = "leveling_event_periods"
    __table_args__ = (
        CheckConstraint("accepted_power >= 0", name="power"),
        CheckConstraint("accepted = 1 OR accepted_power = 0", name="rejected"),
        {"mysql_engine": "InnoDB"},
    )

    event_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_events.event_id", ondelete="CASCADE"), primary_key=True
    )
    period_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_periods.period_id", ondelete="RESTRICT"), primary_key=True
    )
    accepted: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(String(64))
    accepted_power: Mapped[int] = mapped_column(Amount, default=0, server_default="0")


class MessageReceipt(LevelingBase):
    __tablename__ = "leveling_message_receipts"
    __table_args__ = (
        CheckConstraint("route IN ('text','action')", name="route"),
        Index("ix_leveling_message_receipts_expiry", "expires_at", "message_id"),
        {"mysql_engine": "InnoDB"},
    )

    message_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    route: Mapped[str] = mapped_column(String(8))
    generation: Mapped[int] = mapped_column(ID)
    operation_key: Mapped[str] = mapped_column(String(191))
    processed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    outcome: Mapped[str] = mapped_column(String(32))
