from __future__ import annotations

from datetime import datetime
from typing import cast

import discord
import pytest

from app.core.bot import AsteroidBot
from app.database.repositories.role_panel import (
    RolePanelCategoryDetail,
    RolePanelRoleData,
)
from app.features.rolepanel.service import (
    PANEL_CATEGORY_LIMIT,
    RolePanelService,
    build_boost_role_removal_plan,
    build_role_sync_plan,
    get_visible_category_roles,
    member_needs_boost,
    sort_roles_by_hierarchy,
)
from app.features.rolepanel.views import (
    CATEGORY_BUTTON_LABEL_LIMIT,
    RolePanelSelectView,
    RolePanelView,
    build_role_select_options,
)


class FakeRole:
    def __init__(self, role_id: int, position: int, managed: bool = False):
        self.id = role_id
        self.name = f"role-{role_id}"
        self.position = position
        self.managed = managed
        self.mention = f"<@&{role_id}>"

    def __lt__(self, other: object) -> bool:
        return isinstance(other, FakeRole) and self.position < other.position


class FakeGuild:
    def __init__(self, roles: list[FakeRole], top_role: FakeRole):
        self.id = 500
        self.default_role = roles[0]
        self.me = type("FakeMe", (), {"top_role": top_role})()
        self._roles = {role.id: role for role in roles}
        self.get_role_calls: list[int] = []

    def get_role(self, role_id: int) -> FakeRole | None:
        self.get_role_calls.append(role_id)
        return self._roles.get(role_id)


class FakeMember:
    def __init__(
        self,
        guild: FakeGuild,
        roles: list[FakeRole],
        member_id: int = 100,
        premium_since: datetime | None = None,
    ):
        self.id = member_id
        self.guild = guild
        self.roles = roles
        self.premium_since = premium_since
        self.remove_roles_calls: list[tuple[tuple[FakeRole, ...], str | None, bool]] = []

    async def remove_roles(
        self,
        *roles: FakeRole,
        reason: str | None = None,
        atomic: bool = True,
    ) -> None:
        self.remove_roles_calls.append((roles, reason, atomic))


class FakeRolePanelRepository:
    def __init__(self, categories: list[RolePanelCategoryDetail]):
        self.categories = categories

    async def get_categories(self) -> list[RolePanelCategoryDetail]:
        return self.categories


def build_category(
    *,
    roles: list[int],
    requires_boost: bool = False,
    category_id: int = 1,
    name: str = "通知",
) -> RolePanelCategoryDetail:
    now = datetime.now()
    return RolePanelCategoryDetail(
        category_id=category_id,
        name=name,
        description=None,
        display_order=1,
        requires_boost=requires_boost,
        created_at=now,
        updated_at=now,
        roles=[RolePanelRoleData(1, role_id, index, now, now) for index, role_id in enumerate(roles)],
    )


def test_member_needs_boost_checks_member_premium_since() -> None:
    roles = [FakeRole(1, 1), FakeRole(10, 10), FakeRole(20, 20)]
    guild = FakeGuild(roles, FakeRole(999, 999))
    member = FakeMember(guild, [roles[0], roles[1], roles[2]])
    category = build_category(roles=[20], requires_boost=True)

    assert member_needs_boost(cast(discord.Member, member), category) is True

    member.premium_since = datetime.now()

    assert member_needs_boost(cast(discord.Member, member), category) is False


def test_build_role_select_options_only_includes_category_roles() -> None:
    roles = [FakeRole(1, 1), FakeRole(10, 10), FakeRole(20, 20), FakeRole(30, 30)]
    guild = FakeGuild(roles, FakeRole(999, 999))
    member = FakeMember(guild, [roles[0], roles[1], roles[3]])
    category = build_category(roles=[10, 20])

    options = build_role_select_options(category, cast(discord.Member, member))

    assert [option.value for option in options] == ["20", "10"]
    assert [option.default for option in options] == [False, True]


def test_role_panel_select_view_uses_prebuilt_options() -> None:
    roles = [FakeRole(1, 1), FakeRole(10, 10), FakeRole(20, 20)]
    guild = FakeGuild(roles, FakeRole(999, 999))
    member = FakeMember(guild, [roles[0]])
    category = build_category(roles=[10, 20])
    options = build_role_select_options(category, cast(discord.Member, member))
    get_role_call_count = len(guild.get_role_calls)

    view = RolePanelSelectView(
        RolePanelService(bot=cast(AsteroidBot, object())),
        category,
        cast(discord.Member, member),
        options,
    )

    assert len(view.children) == 1
    assert len(guild.get_role_calls) == get_role_call_count


def test_role_panel_view_truncates_category_button_labels() -> None:
    category = build_category(roles=[10], name="あ" * (CATEGORY_BUTTON_LABEL_LIMIT + 1))

    view = RolePanelView(RolePanelService(bot=cast(AsteroidBot, object())), [category])

    button = cast(discord.ui.Button, view.children[0])
    assert button.label == "あ" * CATEGORY_BUTTON_LABEL_LIMIT


def test_build_role_sync_plan_syncs_only_category_manageable_roles() -> None:
    default_role = FakeRole(1, 1)
    current_role = FakeRole(10, 10)
    added_role = FakeRole(20, 20)
    category_outside_role = FakeRole(30, 30)
    too_high_role = FakeRole(40, 400)
    managed_role = FakeRole(50, 50, managed=True)
    bot_top_role = FakeRole(999, 100)
    guild = FakeGuild(
        [default_role, current_role, added_role, category_outside_role, too_high_role, managed_role],
        bot_top_role,
    )
    member = FakeMember(guild, [default_role, current_role])
    category = build_category(roles=[10, 20, 40, 50])

    plan = build_role_sync_plan(cast(discord.Member, member), category, {20, 30, 40, 50})

    assert [role.id for role in plan.add_roles] == [20]
    assert [role.id for role in plan.remove_roles] == [10]
    assert plan.ignored_role_ids == {30}
    assert plan.unmanageable_role_ids == {40, 50}


def test_build_boost_role_removal_plan_selects_owned_manageable_roles_once() -> None:
    default_role = FakeRole(1, 1)
    boost_role = FakeRole(10, 10)
    normal_role = FakeRole(20, 20)
    too_high_role = FakeRole(30, 300)
    managed_role = FakeRole(40, 40, managed=True)
    guild = FakeGuild(
        [default_role, boost_role, normal_role, too_high_role, managed_role],
        FakeRole(999, 100),
    )
    member = FakeMember(guild, [default_role, boost_role, normal_role, too_high_role, managed_role])
    categories = [
        build_category(roles=[10, 30, 40], requires_boost=True, category_id=1),
        build_category(roles=[10], requires_boost=True, category_id=2),
        build_category(roles=[20], requires_boost=False, category_id=3),
    ]

    plan = build_boost_role_removal_plan(cast(discord.Member, member), categories)

    assert [role.id for role in plan.remove_roles] == [10]
    assert plan.unmanageable_role_ids == {30, 40}


@pytest.mark.asyncio
async def test_remove_boost_required_roles_removes_planned_roles() -> None:
    default_role = FakeRole(1, 1)
    boost_role = FakeRole(10, 10)
    guild = FakeGuild([default_role, boost_role], FakeRole(999, 100))
    member = FakeMember(guild, [default_role, boost_role])
    repository = FakeRolePanelRepository([build_category(roles=[10], requires_boost=True)])
    bot = cast(AsteroidBot, type("FakeBot", (), {"db": type("FakeDB", (), {"role_panel": repository})()})())
    service = RolePanelService(bot)

    removed_roles = await service.remove_boost_required_roles(cast(discord.Member, member))

    assert [role.id for role in removed_roles] == [10]
    assert len(member.remove_roles_calls) == 1
    roles, reason, atomic = member.remove_roles_calls[0]
    assert [role.id for role in roles] == [10]
    assert reason is not None and "サーバーブースト解除" in reason
    assert atomic is False


def test_build_role_sync_plan_uses_visible_sorted_role_limit() -> None:
    default_role = FakeRole(1, 1)
    hidden_current_role = FakeRole(10, 1)
    visible_added_role = FakeRole(35, 200)
    middle_roles = [FakeRole(role_id, 100 - role_id) for role_id in range(11, 35)]
    bot_top_role = FakeRole(999, 999)
    guild = FakeGuild([default_role, hidden_current_role, *middle_roles, visible_added_role], bot_top_role)
    member = FakeMember(guild, [default_role, hidden_current_role])
    category = build_category(roles=[10, *range(11, 35), 35])

    plan = build_role_sync_plan(cast(discord.Member, member), category, {35})

    assert [role.id for role in plan.add_roles] == [35]
    assert plan.remove_roles == []
    assert plan.ignored_role_ids == set()
    assert 10 not in {role.role_id for role in get_visible_category_roles(category, cast(discord.Guild, guild))}


def test_build_panel_embed_shows_only_category_name_and_roles() -> None:
    category = build_category(roles=[10, 20], requires_boost=True)
    category.description = "説明"
    service = RolePanelService(bot=cast(AsteroidBot, object()))

    embed = service.build_panel_embed([category])

    field = embed.fields[0]
    assert field.name == "通知"
    assert "[ID:" not in field.name
    field_value = field.value or ""
    assert "説明" not in field_value
    assert "必要ロール" not in field_value
    assert "<@&10>" in field_value
    assert "<@&20>" in field_value
    assert "<@&30>" not in field_value


def test_build_panel_embed_limits_categories_to_discord_field_limit() -> None:
    categories = [
        build_category(roles=[10], category_id=index, name=f"カテゴリ{index}")
        for index in range(1, PANEL_CATEGORY_LIMIT + 2)
    ]
    service = RolePanelService(bot=cast(AsteroidBot, object()))

    embed = service.build_panel_embed(categories)

    assert len(embed.fields) == PANEL_CATEGORY_LIMIT
    assert embed.fields[-1].name == f"カテゴリ{PANEL_CATEGORY_LIMIT}"
    assert f"表示対象は先頭{PANEL_CATEGORY_LIMIT}カテゴリです。" in (embed.description or "")


def test_sort_roles_by_hierarchy_orders_higher_roles_first() -> None:
    role_low = FakeRole(10, 10)
    role_high = FakeRole(20, 20)
    role_middle = FakeRole(30, 15)
    guild = FakeGuild([FakeRole(1, 1), role_low, role_high, role_middle], FakeRole(999, 999))
    category = build_category(roles=[10, 20, 30])

    sorted_roles = sort_roles_by_hierarchy(category.roles, cast(discord.Guild, guild))

    assert [role.role_id for role in sorted_roles] == [20, 30, 10]
