from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import ID, Amount, LevelingBase, UTCDateTime


class MigrationRun(LevelingBase):
    __tablename__ = "leveling_migration_runs"
    __table_args__ = (
        UniqueConstraint("source_digest"),
        {"mysql_engine": "InnoDB"},
    )

    migration_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=True)
    source_revision: Mapped[str] = mapped_column(String(64))
    source_digest: Mapped[str] = mapped_column(String(64))
    target_generation: Mapped[int] = mapped_column(ID)
    cutover_at: Mapped[datetime] = mapped_column(UTCDateTime)
    status: Mapped[str] = mapped_column(String(32))
    checksums: Mapped[dict[str, object]] = mapped_column(JSON)


class MigrationItem(LevelingBase):
    __tablename__ = "leveling_migration_items"
    __table_args__ = ({"mysql_engine": "InnoDB"},)

    migration_id: Mapped[int] = mapped_column(
        ID, ForeignKey("leveling_migration_runs.migration_id", ondelete="RESTRICT"), primary_key=True
    )
    source_table: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(191), primary_key=True)
    source_values: Mapped[dict[str, object]] = mapped_column(JSON)
    target_keys: Mapped[dict[str, object]] = mapped_column(JSON)
    applied_at: Mapped[datetime] = mapped_column(UTCDateTime)


class ImportItem(LevelingBase):
    __tablename__ = "leveling_import_items"
    __table_args__ = (
        UniqueConstraint("source_kind", "source_guild_id", "source_user_id", "source_digest", "calculation_version"),
        CheckConstraint("applied_shard >= 0", name="shard"),
        {"mysql_engine": "InnoDB"},
    )

    source_kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_guild_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    source_user_id: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    approved_revision: Mapped[int] = mapped_column(ID, primary_key=True, autoincrement=False)
    source_digest: Mapped[str] = mapped_column(String(64))
    calculation_version: Mapped[str] = mapped_column(String(64))
    applied_shard: Mapped[int] = mapped_column(Amount, default=0, server_default="0")
    operation_key: Mapped[str] = mapped_column(
        String(191), ForeignKey("leveling_operations.operation_key", ondelete="RESTRICT")
    )
