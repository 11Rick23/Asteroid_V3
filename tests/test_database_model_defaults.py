from __future__ import annotations

from typing import Any, cast

from sqlalchemy import Column, Table
from sqlalchemy.schema import DefaultClause

from app.database.models.given_stars import GivenStarModel
from app.database.models.monthly_action_powers import MonthlyActionPowerModel
from app.database.models.monthly_powers import MonthlyPowerModel
from app.database.models.role_panel import RolePanelCategoryModel, RolePanelRoleModel
from app.database.models.star_grades import StarGradeModel
from app.database.models.starred_messages import StarredMessageModel
from app.database.models.user_birthdays import UserBirthdayModel
from app.database.models.user_roles import UserRoleModel
from app.database.models.voice_xp_limits import VoiceXPLimitModel
from app.database.models.xp_boosts import XPBoostModel


def model_table(model: type[Any]) -> Table:
    return cast(Table, model.__table__)


def column(model: type[Any], name: str) -> Column[Any]:
    return model_table(model).c[name]


def server_default(model: type[Any], name: str) -> str:
    default = column(model, name).server_default
    assert isinstance(default, DefaultClause)
    return str(default.arg)


def test_timestamp_columns_use_database_defaults() -> None:
    models = (
        GivenStarModel,
        MonthlyActionPowerModel,
        MonthlyPowerModel,
        RolePanelCategoryModel,
        RolePanelRoleModel,
        StarGradeModel,
        StarredMessageModel,
        UserBirthdayModel,
        UserRoleModel,
        VoiceXPLimitModel,
        XPBoostModel,
    )

    for model in models:
        assert server_default(model, "created_at") == "CURRENT_TIMESTAMP"
        assert server_default(model, "updated_at") == "CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
        assert column(model, "updated_at").server_onupdate is not None


def test_zero_value_columns_use_database_defaults() -> None:
    default_zero_columns = (
        (GivenStarModel, "given_star_amount"),
        (MonthlyActionPowerModel, "action_power"),
        (MonthlyPowerModel, "text_power"),
        (MonthlyPowerModel, "voice_power"),
        (RolePanelCategoryModel, "display_order"),
        (RolePanelCategoryModel, "requires_boost"),
        (RolePanelRoleModel, "display_order"),
        (StarGradeModel, "prestige"),
        (StarGradeModel, "grade"),
        (StarGradeModel, "shard"),
        (StarGradeModel, "text_shard"),
        (StarGradeModel, "voice_shard"),
        (StarGradeModel, "bonus_shard"),
        (StarredMessageModel, "star_amount"),
        (VoiceXPLimitModel, "voice_shard"),
        (VoiceXPLimitModel, "bonus_shard"),
        (VoiceXPLimitModel, "voice_power"),
        (VoiceXPLimitModel, "half_notify"),
        (VoiceXPLimitModel, "full_notify"),
    )

    for model, name in default_zero_columns:
        assert server_default(model, name) == "0"
