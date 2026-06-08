from __future__ import annotations

from datetime import datetime

from app.database.repositories.role_panel import (
    RolePanelCategoryDetail,
    RolePanelRoleData,
)
from app.features.rolepanel.service import (
    RolePanelService,
    build_role_sync_plan,
    member_needs_boost,
    sort_roles_by_hierarchy,
)
from app.features.rolepanel.views import RolePanelSelectView, build_role_select_options


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
    def __init__(self, roles: list[FakeRole], top_role: FakeRole, premium_subscriber_role: FakeRole | None = None):
        self.default_role = roles[0]
        self.me = type("FakeMe", (), {"top_role": top_role})()
        self.premium_subscriber_role = premium_subscriber_role
        self._roles = {role.id: role for role in roles}
        self.get_role_calls: list[int] = []

    def get_role(self, role_id: int) -> FakeRole | None:
        self.get_role_calls.append(role_id)
        return self._roles.get(role_id)


class FakeMember:
    def __init__(self, guild: FakeGuild, roles: list[FakeRole], member_id: int = 100):
        self.id = member_id
        self.guild = guild
        self.roles = roles


def build_category(*, roles: list[int], requires_boost: bool = False) -> RolePanelCategoryDetail:
    now = datetime.now()
    return RolePanelCategoryDetail(
        category_id=1,
        name="通知",
        description=None,
        display_order=1,
        requires_boost=requires_boost,
        created_at=now,
        updated_at=now,
        roles=[RolePanelRoleData(1, role_id, index, now, now) for index, role_id in enumerate(roles)],
    )


def test_member_needs_boost_checks_guild_premium_subscriber_role() -> None:
    roles = [FakeRole(1, 1), FakeRole(10, 10), FakeRole(20, 20)]
    guild = FakeGuild(roles, FakeRole(999, 999), premium_subscriber_role=roles[2])
    member = FakeMember(guild, [roles[0], roles[1]])
    category = build_category(roles=[20], requires_boost=True)

    assert member_needs_boost(member, category) is True

    member.roles.append(roles[2])

    assert member_needs_boost(member, category) is False


def test_build_role_select_options_only_includes_category_roles() -> None:
    roles = [FakeRole(1, 1), FakeRole(10, 10), FakeRole(20, 20), FakeRole(30, 30)]
    guild = FakeGuild(roles, FakeRole(999, 999))
    member = FakeMember(guild, [roles[0], roles[1], roles[3]])
    category = build_category(roles=[10, 20])

    options = build_role_select_options(category, member)

    assert [option.value for option in options] == ["20", "10"]
    assert [option.default for option in options] == [False, True]


def test_role_panel_select_view_uses_prebuilt_options() -> None:
    roles = [FakeRole(1, 1), FakeRole(10, 10), FakeRole(20, 20)]
    guild = FakeGuild(roles, FakeRole(999, 999))
    member = FakeMember(guild, [roles[0]])
    category = build_category(roles=[10, 20])
    options = build_role_select_options(category, member)
    get_role_call_count = len(guild.get_role_calls)

    view = RolePanelSelectView(RolePanelService(bot=object()), category, member, options)

    assert len(view.children) == 1
    assert len(guild.get_role_calls) == get_role_call_count


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

    plan = build_role_sync_plan(member, category, {20, 30, 40, 50})

    assert [role.id for role in plan.add_roles] == [20]
    assert [role.id for role in plan.remove_roles] == [10]
    assert plan.ignored_role_ids == {30}
    assert plan.unmanageable_role_ids == {40, 50}


def test_build_panel_embed_shows_only_category_name_and_roles() -> None:
    category = build_category(roles=[10, 20], requires_boost=True)
    category.description = "説明"
    service = RolePanelService(bot=object())

    embed = service.build_panel_embed([category])

    field = embed.fields[0]
    assert field.name == "通知"
    assert "[ID:" not in field.name
    assert "説明" not in field.value
    assert "必要ロール" not in field.value
    assert "<@&10>" in field.value
    assert "<@&20>" in field.value
    assert "<@&30>" not in field.value


def test_sort_roles_by_hierarchy_orders_higher_roles_first() -> None:
    role_low = FakeRole(10, 10)
    role_high = FakeRole(20, 20)
    role_middle = FakeRole(30, 15)
    guild = FakeGuild([FakeRole(1, 1), role_low, role_high, role_middle], FakeRole(999, 999))
    category = build_category(roles=[10, 20, 30])

    sorted_roles = sort_roles_by_hierarchy(category.roles, guild)

    assert [role.role_id for role in sorted_roles] == [20, 30, 10]
