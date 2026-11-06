from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import ID, Amount, LevelingBase, UTCDateTime


class VoiceState(LevelingBase):
    __tablename__ = "leveling_voice_state"
    __table_args__ = (
        CheckConstraint("state IN ('tracking','suspended','reconciling','stopped')", name="state"),
        CheckConstraint("consumed_offset_us >= 0 AND eligible_elapsed_us >= 0", name="duration"),
        CheckConstraint(
            "(prepared_grant_seq IS NULL AND prepared_random IS NULL) OR "
            "(prepared_grant_seq IS NOT NULL AND prepared_random IS NOT NULL AND "
            "prepared_grant_seq = next_grant_seq AND prepared_random >= 0)",
            name="prepared",
        ),
        {"mysql_engine": "InnoDB"},
    )

    user_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_accounts.user_id", ondelete="RESTRICT"), primary_key=True
    )
    measurement_epoch: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16))
    last_channel_id: Mapped[int | None] = mapped_column(
        ID, ForeignKey("leveling_channels.channel_id", ondelete="RESTRICT")
    )
    last_confirmed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    checkpoint_version: Mapped[int] = mapped_column(ID, default=0, server_default="0")
    pending_cycle: Mapped[int] = mapped_column(ID, default=0, server_default="0")
    cap_notice_attempted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    next_grant_seq: Mapped[int] = mapped_column(ID, default=1, server_default="1")
    consumed_segment_seq: Mapped[int] = mapped_column(ID, default=0, server_default="0")
    consumed_offset_us: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    prepared_grant_seq: Mapped[int | None] = mapped_column(ID)
    prepared_random: Mapped[int | None] = mapped_column(Amount)
    calculation_version: Mapped[str] = mapped_column(String(64))
    eligible_elapsed_us: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")


class VoiceSegmentRow(LevelingBase):
    __tablename__ = "leveling_voice_segments"
    __table_args__ = (
        CheckConstraint("start_at < end_at AND duration_us > 0", name="duration"),
        {"mysql_engine": "InnoDB"},
    )

    user_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_voice_state.user_id", ondelete="RESTRICT"), primary_key=True
    )
    segment_seq: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    start_at: Mapped[datetime] = mapped_column(UTCDateTime)
    end_at: Mapped[datetime] = mapped_column(UTCDateTime)
    channel_id: Mapped[int] = mapped_column(ID, ForeignKey("leveling_channels.channel_id", ondelete="RESTRICT"))
    duration_us: Mapped[int] = mapped_column(BigInteger)
    rate_snapshot: Mapped[str] = mapped_column(Text)
    shard_eligible: Mapped[bool] = mapped_column(Boolean)
    power_eligible: Mapped[bool] = mapped_column(Boolean)
    grant_seq: Mapped[int] = mapped_column(ID)


class VoiceGrant(LevelingBase):
    __tablename__ = "leveling_voice_grants"
    __table_args__ = (
        UniqueConstraint("operation_key"),
        Index("ix_leveling_voice_grants_committed", "committed_at", "user_id", "grant_seq"),
        {"mysql_engine": "InnoDB"},
    )

    user_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_voice_state.user_id", ondelete="RESTRICT"), primary_key=True
    )
    grant_seq: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    measurement_epoch: Mapped[str] = mapped_column(String(64))
    operation_key: Mapped[str] = mapped_column(String(191))
    period_end: Mapped[datetime] = mapped_column(UTCDateTime)
    committed_at: Mapped[datetime] = mapped_column(UTCDateTime)


class VoicePending(LevelingBase):
    __tablename__ = "leveling_voice_pending"
    __table_args__ = (
        CheckConstraint("origin IN ('native','legacy')", name="origin"),
        CheckConstraint("voice_shard >= 0 AND bonus_shard >= 0 AND power_meter >= 0", name="balances"),
        Index("ix_leveling_voice_pending_month", "month_period_id", "user_id"),
        {"mysql_engine": "InnoDB"},
    )

    user_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_accounts.user_id", ondelete="RESTRICT"), primary_key=True
    )
    month_period_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_periods.period_id", ondelete="RESTRICT"), primary_key=True
    )
    origin: Mapped[str] = mapped_column(String(8), primary_key=True)
    voice_shard: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    bonus_shard: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    power_meter: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    version: Mapped[int] = mapped_column(ID, default=0, server_default="0")


class Claim(LevelingBase):
    __tablename__ = "leveling_claims"
    __table_args__ = (
        UniqueConstraint("operation_key"),
        CheckConstraint("`trigger` IN ('manual','month_close','late_closed_month')", name="trigger"),
        CheckConstraint(
            "(`trigger` = 'manual' AND month_period_id IS NULL) OR "
            "(`trigger` <> 'manual' AND month_period_id IS NOT NULL)",
            name="month_scope",
        ),
        CheckConstraint("shard_amount >= 0 AND bonus_amount >= 0 AND power_released >= 0", name="amounts"),
        Index("ix_leveling_claims_user", "user_id", "committed_at"),
        {"mysql_engine": "InnoDB"},
    )

    claim_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    operation_key: Mapped[str] = mapped_column(String(191))
    user_id: Mapped[int] = mapped_column(ID, ForeignKey("leveling_accounts.user_id", ondelete="RESTRICT"))
    trigger: Mapped[str] = mapped_column(String(32))
    month_period_id: Mapped[int | None] = mapped_column(
        ID, ForeignKey("leveling_periods.period_id", ondelete="RESTRICT")
    )
    shard_amount: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    bonus_amount: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    power_released: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    committed_at: Mapped[datetime] = mapped_column(UTCDateTime)


class ClaimItem(LevelingBase):
    __tablename__ = "leveling_claim_items"
    __table_args__ = (
        CheckConstraint("origin IN ('native','legacy')", name="origin"),
        CheckConstraint(
            "before_voice_shard >= claimed_voice_shard AND claimed_voice_shard >= 0 AND "
            "before_bonus_shard >= claimed_bonus_shard AND claimed_bonus_shard >= 0 AND "
            "before_power_meter >= claimed_power_meter AND claimed_power_meter >= 0",
            name="amounts",
        ),
        {"mysql_engine": "InnoDB"},
    )

    claim_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_claims.claim_id", ondelete="RESTRICT"), primary_key=True
    )
    month_period_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_periods.period_id", ondelete="RESTRICT"), primary_key=True
    )
    origin: Mapped[str] = mapped_column(String(8), primary_key=True)
    before_voice_shard: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    before_bonus_shard: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    before_power_meter: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    claimed_voice_shard: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    claimed_bonus_shard: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    claimed_power_meter: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
