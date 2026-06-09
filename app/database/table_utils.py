from __future__ import annotations

from typing import Any, cast

from sqlalchemy import Table


def model_table(model: type[Any]) -> Table:
    return cast(Table, model.__table__)
