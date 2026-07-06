from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from app.database.repositories.role_panel import RolePanelCategoryDetail, RolePanelRoleData
from app.features.rolepanel.service import (
    build_boost_role_removal_plan,
    build_role_sync_plan,
    get_visible_category_roles,
    member_needs_boost,
)
from tests.support.discord_fakes import FakeGuild, FakeMember, FakeRole


def _role_data(role_id: int, display_order: int = 0) -> RolePanelRoleData:
    now = datetime(2026, 6, 23)
    return RolePanelRoleData(
        category_id=1,
        role_id=role_id,
        display_order=display_order,
        created_at=now,
        updated_at=now,
    )


def _category(
    *,
    requires_boost: bool = False,
    roles: list[RolePanelRoleData] | None = None,
) -> RolePanelCategoryDetail:
    now = datetime(2026, 6, 23)
    return RolePanelCategoryDetail(
        category_id=1,
        name="カテゴリ",
        description=None,
        display_order=0,
        requires_boost=requires_boost,
        created_at=now,
        updated_at=now,
        roles=roles or [],
    )


def test_requires_boost():
    """ブースト必須カテゴリでは premium_since がない member を条件不足として扱う。"""
    # 機能要件：ブースト必須カテゴリでは未ブースト member を条件不足として扱う。
    # Given
    guild = FakeGuild()
    member = FakeMember(guild=guild)

    # When / Then
    assert member_needs_boost(cast(Any, member), _category(requires_boost=True)) is True
    assert member_needs_boost(cast(Any, member), _category(requires_boost=False)) is False


def test_sorts_visible_roles():
    """表示ロールは guild のロール階層順で並べ、Discord select 上限の 25 件に丸める。"""
    # 機能要件：ロールパネルの表示候補は guild のロール階層順で並べる。
    # 非機能要件：Discord select の上限に合わせて表示ロールを 25 件までに制限する。
    # Given
    guild_roles = [FakeRole(id=role_id, position=role_id) for role_id in range(1, 31)]
    guild = FakeGuild(roles=guild_roles)
    category = _category(roles=[_role_data(role_id) for role_id in range(1, 31)])

    # When
    visible_roles = get_visible_category_roles(category, cast(Any, guild))

    # Then
    assert [role.role_id for role in visible_roles] == list(range(30, 5, -1))


def test_builds_sync_plan():
    """選択状態と現在ロールから追加、削除、カテゴリ外選択を分離する。"""
    # 機能要件：選択状態と現在ロールから追加・削除対象を計画する。
    # 非機能要件：カテゴリ外の選択 ID は同期対象にせず記録する。
    # Given
    add_role = FakeRole(id=1, position=10)
    keep_role = FakeRole(id=2, position=9)
    remove_role = FakeRole(id=3, position=8)
    guild = FakeGuild(roles=[add_role, keep_role, remove_role])
    member = FakeMember(guild=guild, roles=[keep_role, remove_role])
    category = _category(roles=[_role_data(1), _role_data(2), _role_data(3)])

    # When
    plan = build_role_sync_plan(cast(Any, member), category, {1, 2, 999})

    # Then
    assert [role.id for role in plan.add_roles] == [1]
    assert [role.id for role in plan.remove_roles] == [3]
    assert plan.ignored_role_ids == {999}
    assert plan.unmanageable_role_ids == set()


def test_skips_unmanageable():
    """BOT が管理できないロールは同期対象から外し、管理不能 ID として記録する。"""
    # 非機能要件：BOT が管理できないロールを追加・削除対象にしない。
    # Given
    high_role = FakeRole(id=1, position=1000)
    guild = FakeGuild(roles=[high_role], bot_top_role=FakeRole(id=999, position=100))
    member = FakeMember(guild=guild)
    category = _category(roles=[_role_data(1)])

    # When
    plan = build_role_sync_plan(cast(Any, member), category, {1})

    # Then
    assert plan.add_roles == []
    assert plan.unmanageable_role_ids == {1}


def test_builds_boost_removal():
    """ブースト解除時はブースト必須カテゴリの保持ロールだけを削除計画に入れる。"""
    # 機能要件：ブースト解除時はブースト必須カテゴリの保持ロールを削除対象にする。
    # 非機能要件：通常カテゴリのロールはブースト解除処理で削除しない。
    # Given
    boost_role = FakeRole(id=1, position=10)
    normal_role = FakeRole(id=2, position=9)
    guild = FakeGuild(roles=[boost_role, normal_role])
    member = FakeMember(guild=guild, roles=[boost_role, normal_role])
    categories = [
        _category(requires_boost=True, roles=[_role_data(1)]),
        _category(requires_boost=False, roles=[_role_data(2)]),
    ]

    # When
    plan = build_boost_role_removal_plan(cast(Any, member), categories)

    # Then
    assert [role.id for role in plan.remove_roles] == [1]
    assert plan.unmanageable_role_ids == set()
