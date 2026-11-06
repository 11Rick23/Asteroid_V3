"""MySQLが引用符付きで反映するDECIMAL defaultの意味を比較する。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from alembic.migration import MigrationContext
from sqlalchemy import Column, FetchedValue

from app.database.models.leveling_v2.base import Amount


def compare_server_default(
    context: MigrationContext,
    inspected: Column[Any],
    metadata: Column[Any],
    inspected_default: str | None,
    metadata_default: FetchedValue | None,
    rendered_metadata_default: str | None,
) -> bool | None:
    if not isinstance(metadata.type, Amount) or inspected_default is None or rendered_metadata_default is None:
        return None
    try:
        actual = Decimal(inspected_default.strip("'"))
        expected = Decimal(rendered_metadata_default.strip("'"))
    except InvalidOperation:
        return None
    if not actual.is_finite() or not expected.is_finite():
        return None
    return actual != expected
