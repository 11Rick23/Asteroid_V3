from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from app.database.repositories.role_panel import RolePanelCategoryDetail, RolePanelRoleData
from app.features.rolepanel.service import (
    RolePanelService,
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
    category_id: int = 1,
    name: str = "カテゴリ",
    description: str | None = None,
    display_order: int = 0,
    requires_boost: bool = False,
    roles: list[RolePanelRoleData] | None = None,
) -> RolePanelCategoryDetail:
    now = datetime(2026, 6, 23)
    return RolePanelCategoryDetail(
        category_id=category_id,
        name=name,
        description=description,
        display_order=display_order,
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


def test_builds_category_settings_embed():
    """カテゴリ設定一覧はカテゴリ名、説明文、表示順を管理用に表示する。"""
    # 機能要件：rolepanel list は全カテゴリのカテゴリ名、説明文、表示順を一覧表示する。
    # Given
    service = RolePanelService(cast(Any, object()))
    categories = [
        _category(category_id=1, name="通知", description="通知ロールです。", display_order=20),
        _category(category_id=2, name="イベント", description=None, display_order=10),
    ]

    # When
    embeds = service.build_category_settings_embeds(categories)

    # Then
    assert len(embeds) == 1
    embed = embeds[0]
    assert embed.title == "ロールパネルカテゴリ設定一覧"
    assert [field.name for field in embed.fields] == ["通知", "イベント"]
    assert embed.fields[0].value == "表示順: `20`\n説明文:\n通知ロールです。"
    assert embed.fields[1].value == "表示順: `10`\n説明文:\n説明未設定"


def test_builds_category_settings_embed_pages():
    """カテゴリ設定一覧は Discord の embed field 上限を超えるカテゴリも分割して表示する。"""
    # 機能要件：rolepanel list は 25 件を超えるカテゴリも続きの embed に分割して一覧表示する。
    # Given
    service = RolePanelService(cast(Any, object()))
    categories = [_category(category_id=index, name=f"カテゴリ{index}") for index in range(1, 27)]

    # When
    embeds = service.build_category_settings_embeds(categories)

    # Then
    assert [embed.title for embed in embeds] == [
        "ロールパネルカテゴリ設定一覧 (1/2)",
        "ロールパネルカテゴリ設定一覧 (2/2)",
    ]
    assert len(embeds[0].fields) == 25
    assert [field.name for field in embeds[1].fields] == ["カテゴリ26"]
