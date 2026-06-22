from __future__ import annotations

from typing import Any, cast

from sqlalchemy import Table

from app.database.models.given_stars import GivenStarModel
from app.database.models.role_panel import RolePanelCategoryModel, RolePanelRoleModel
from app.database.models.star_grades import StarGradeModel
from app.database.models.starred_messages import StarredMessageModel
from app.database.models.user_birthdays import UserBirthdayModel
from app.database.models.xp_boosts import XPBoostModel


def index_columns(table: Table) -> dict[str, tuple[str, ...]]:
    return {index.name or "": tuple(column.name for column in index.columns) for index in table.indexes}


def model_table(model: type[Any]) -> Table:
    return cast(Table, model.__table__)


def test_star_grade_ranking_index() -> None:
    indexes = index_columns(model_table(StarGradeModel))

    assert indexes["idx_star_grades_ranking"] == ("prestige", "grade", "shard")


def test_given_star_ranking_index() -> None:
    indexes = index_columns(model_table(GivenStarModel))

    assert indexes["idx_given_stars_given_star_amount"] == ("given_star_amount",)


def test_starred_message_query_indexes() -> None:
    indexes = index_columns(model_table(StarredMessageModel))

    assert indexes["idx_starred_messages_star_amount"] == ("star_amount",)
    assert indexes["idx_starred_messages_user_id"] == ("user_id",)


def test_role_panel_order_indexes() -> None:
    category_indexes = index_columns(model_table(RolePanelCategoryModel))
    role_indexes = index_columns(model_table(RolePanelRoleModel))

    assert category_indexes["idx_role_panel_categories_display_order"] == ("display_order",)
    assert role_indexes["idx_role_panel_roles_category_order"] == ("category_id", "display_order", "role_id")


def test_birthday_lookup_index() -> None:
    indexes = index_columns(model_table(UserBirthdayModel))

    assert indexes["idx_user_birthdays_date"] == ("date",)


def test_xp_boost_expiration_index() -> None:
    indexes = index_columns(model_table(XPBoostModel))

    assert indexes["idx_xp_boosts_boost_end_time"] == ("boost_end_time",)
