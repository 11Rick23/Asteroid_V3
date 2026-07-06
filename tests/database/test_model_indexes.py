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
    """star grade ranking 用の複合 index を model に定義する。"""
    # 非機能要件：star grade の ranking query は prestige / grade / shard の複合 index を利用できる。
    # Given
    table = model_table(StarGradeModel)

    # When
    indexes = index_columns(table)

    # Then
    assert indexes["idx_star_grades_ranking"] == ("prestige", "grade", "shard")


def test_given_star_ranking_index() -> None:
    """given star ranking 用の index を model に定義する。"""
    # 非機能要件：given star の ranking query は given_star_amount index を利用できる。
    # Given
    table = model_table(GivenStarModel)

    # When
    indexes = index_columns(table)

    # Then
    assert indexes["idx_given_stars_given_star_amount"] == ("given_star_amount",)


def test_starred_message_query_indexes() -> None:
    """starred message の検索用 index を model に定義する。"""
    # 非機能要件：starboard の message query は star_amount / user_id index を利用できる。
    # Given
    table = model_table(StarredMessageModel)

    # When
    indexes = index_columns(table)

    # Then
    assert indexes["idx_starred_messages_star_amount"] == ("star_amount",)
    assert indexes["idx_starred_messages_user_id"] == ("user_id",)


def test_role_panel_order_indexes() -> None:
    """role panel 表示順の検索用 index を model に定義する。"""
    # 非機能要件：role panel の表示順 query は category / role の order index を利用できる。
    # Given
    category_table = model_table(RolePanelCategoryModel)
    role_table = model_table(RolePanelRoleModel)

    # When
    category_indexes = index_columns(category_table)
    role_indexes = index_columns(role_table)

    # Then
    assert category_indexes["idx_role_panel_categories_display_order"] == ("display_order",)
    assert role_indexes["idx_role_panel_roles_category_order"] == ("category_id", "display_order", "role_id")


def test_birthday_lookup_index() -> None:
    """誕生日検索用の date index を model に定義する。"""
    # 非機能要件：birthday lookup は date index を利用できる。
    # Given
    table = model_table(UserBirthdayModel)

    # When
    indexes = index_columns(table)

    # Then
    assert indexes["idx_user_birthdays_date"] == ("date",)


def test_xp_boost_expiration_index() -> None:
    """期限切れ XP boost 検索用の index を model に定義する。"""
    # 非機能要件：XP boost の期限切れ検索は boost_end_time index を利用できる。
    # Given
    table = model_table(XPBoostModel)

    # When
    indexes = index_columns(table)

    # Then
    assert indexes["idx_xp_boosts_boost_end_time"] == ("boost_end_time",)
