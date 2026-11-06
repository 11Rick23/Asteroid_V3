"""P2専用metadata。旧Botのmetadataと起動時migrationから分離する。"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import MetaData
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, DECIMAL
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

from app.features.leveling.domain.numbers import amount


class LevelingBase(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Amount(TypeDecorator[int]):
    """Decimal contextやfloatを経由せず整数を保存・復元する。"""

    impl = DECIMAL(65, 0)
    cache_ok = True

    def process_bind_param(self, value: int | None, dialect: Dialect) -> int | None:
        return None if value is None else amount(value)

    def process_result_value(self, value: Decimal | int | None, dialect: Dialect) -> int | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            if not value.is_finite() or value != value.to_integral_value():
                raise ValueError("DB数量が有限の整数ではありません")
        elif type(value) is not int:
            raise ValueError("DB数量の型が不正です")
        return amount(int(value))


class UTCDateTime(TypeDecorator[datetime]):
    impl = DATETIME(fsp=6)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("タイムゾーン付き日時を指定してください")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


ID = BIGINT(unsigned=True)
