from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import ID, Amount, LevelingBase, UTCDateTime


class Installation(LevelingBase):
    __tablename__ = "leveling_installation"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"), {"mysql_engine": "InnoDB"})

    id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    guild_id: Mapped[int] = mapped_column(ID)
    cutover_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    ranking_started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    active_schema_generation: Mapped[int] = mapped_column(ID, default=0, server_default="0")


class Account(LevelingBase):
    __tablename__ = "leveling_accounts"
    __table_args__ = (
        CheckConstraint("text_shard >= 0 AND voice_shard >= 0 AND bonus_shard >= 0", name="balances"),
        CheckConstraint("prestige >= 0 AND grade BETWEEN 0 AND 49 AND shard >= 0", name="growth"),
        {"mysql_engine": "InnoDB"},
    )

    user_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    text_shard: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    voice_shard: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    bonus_shard: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    prestige: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    grade: Mapped[int] = mapped_column(default=0, server_default="0")
    shard: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    version: Mapped[int] = mapped_column(ID, default=0, server_default="0")


Index(
    "ix_leveling_accounts_rank", Account.prestige.desc(), Account.grade.desc(), Account.shard.desc(), Account.user_id
)


class Channel(LevelingBase):
    __tablename__ = "leveling_channels"
    __table_args__ = (CheckConstraint("kind IN ('text', 'voice')", name="kind"), {"mysql_engine": "InnoDB"})

    channel_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    last_name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(16))
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Boost(LevelingBase):
    __tablename__ = "leveling_boosts"
    __table_args__ = (
        CheckConstraint("rate_percent >= 0", name="rate"),
        CheckConstraint("ends_at IS NULL OR starts_at < ends_at", name="interval"),
        Index("ix_leveling_boosts_role_interval", "role_id", "starts_at", "ends_at"),
        {"mysql_engine": "InnoDB"},
    )

    boost_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(ID)
    name: Mapped[str] = mapped_column(String(100))
    rate_percent: Mapped[int] = mapped_column(Amount)
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    version: Mapped[int] = mapped_column(ID, default=0, server_default="0")
