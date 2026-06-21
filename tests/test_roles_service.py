from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import cast

import discord
import pytest

from app.core.bot import AsteroidBot
from app.database.repositories.user_roles import UserRoleData
from app.features.roles.service import JoinRolesService, get_restorable_roles, get_save_role_ids


class FakeRole:
    def __init__(self, role_id: int, position: int):
        self.id = role_id
        self.position = position

    def __lt__(self, other: object) -> bool:
        return isinstance(other, FakeRole) and self.position < other.position


class FakeGuild:
    def __init__(self, roles: list[FakeRole], top_role: FakeRole):
        self.id = 100
        self.default_role = roles[0]
        self.me = SimpleNamespace(top_role=top_role)
        self._roles = {role.id: role for role in roles}

    def get_role(self, role_id: int) -> FakeRole | None:
        return self._roles.get(role_id)


class FakeMember:
    def __init__(self, guild: FakeGuild, roles: list[FakeRole], *, bot: bool = False):
        self.id = 200
        self.guild = guild
        self.roles = roles
        self.bot = bot
        self.add_roles_calls: list[tuple[tuple[FakeRole, ...], str | None, bool]] = []

    async def add_roles(self, *roles: FakeRole, reason: str | None = None, atomic: bool = True) -> None:
        self.add_roles_calls.append((roles, reason, atomic))


class FakeUserRolesRepository:
    def __init__(self, roles_data: list[UserRoleData] | None = None):
        self.roles_data = roles_data or []
        self.saved: tuple[int, list[int]] | None = None
        self.deleted: list[tuple[int, int]] = []

    async def save_user_roles(self, user_id: int, role_ids: list[int]) -> None:
        self.saved = (user_id, role_ids)

    async def get_user_roles(self, user_id: int) -> list[UserRoleData]:
        return self.roles_data

    async def delete_user_role(self, user_id: int, role_id: int) -> None:
        self.deleted.append((user_id, role_id))


def build_role_data(role_id: int) -> UserRoleData:
    now = datetime.now()
    return UserRoleData(user_id=200, role_id=role_id, created_at=now, updated_at=now)


def build_service(repository: FakeUserRolesRepository, *, join_role_ids: list[int] | None = None) -> JoinRolesService:
    bot = cast(
        AsteroidBot,
        SimpleNamespace(
            config=SimpleNamespace(
                roles=SimpleNamespace(
                    ignored_save_role_id_list=[30],
                    join_role_id_list=join_role_ids or [],
                    bot_join_role_id_list=[],
                )
            ),
            db=SimpleNamespace(user_roles=repository),
        ),
    )
    return JoinRolesService(bot)


def test_get_save_role_ids_excludes_default_high_and_ignored_roles() -> None:
    default_role = FakeRole(1, 1)
    saved_role = FakeRole(10, 10)
    ignored_role = FakeRole(30, 30)
    too_high_role = FakeRole(40, 400)
    guild = FakeGuild([default_role, saved_role, ignored_role, too_high_role], FakeRole(999, 100))
    member = FakeMember(guild, [default_role, saved_role, ignored_role, too_high_role])

    role_ids = get_save_role_ids(cast(discord.Member, member), [30])

    assert role_ids == [10]


def test_get_restorable_roles_returns_manageable_roles_and_missing_ids() -> None:
    default_role = FakeRole(1, 1)
    restorable_role = FakeRole(10, 10)
    too_high_role = FakeRole(40, 400)
    guild = FakeGuild([default_role, restorable_role, too_high_role], FakeRole(999, 100))
    member = FakeMember(guild, [default_role])

    roles, missing_role_ids = get_restorable_roles(cast(discord.Member, member), [10, 20, 40])

    assert [role.id for role in roles] == [10]
    assert missing_role_ids == [20]


@pytest.mark.asyncio
async def test_save_user_roles_persists_selected_role_ids() -> None:
    default_role = FakeRole(1, 1)
    saved_role = FakeRole(10, 10)
    guild = FakeGuild([default_role, saved_role], FakeRole(999, 100))
    member = FakeMember(guild, [default_role, saved_role])
    repository = FakeUserRolesRepository()
    service = build_service(repository)

    await service.save_user_roles(cast(discord.Member, member))

    assert repository.saved == (200, [10])


@pytest.mark.asyncio
async def test_restore_user_roles_adds_existing_roles_and_deletes_missing_roles() -> None:
    default_role = FakeRole(1, 1)
    restorable_role = FakeRole(10, 10)
    guild = FakeGuild([default_role, restorable_role], FakeRole(999, 100))
    member = FakeMember(guild, [default_role])
    repository = FakeUserRolesRepository([build_role_data(10), build_role_data(20)])
    service = build_service(repository)

    restored_count = await service.restore_user_roles(cast(discord.Member, member))

    assert restored_count == 1
    assert repository.deleted == [(200, 20)]
    roles, reason, atomic = member.add_roles_calls[0]
    assert [role.id for role in roles] == [10]
    assert reason is not None and "ロール復元機能" in reason
    assert atomic is False


@pytest.mark.asyncio
async def test_give_join_roles_adds_configured_manageable_roles() -> None:
    default_role = FakeRole(1, 1)
    join_role = FakeRole(10, 10)
    guild = FakeGuild([default_role, join_role], FakeRole(999, 100))
    member = FakeMember(guild, [default_role])
    service = build_service(FakeUserRolesRepository(), join_role_ids=[10, 20])

    added_count = await service.give_join_roles(cast(discord.Member, member))

    assert added_count == 1
    roles, reason, atomic = member.add_roles_calls[0]
    assert [role.id for role in roles] == [10]
    assert reason is not None and "自動ロール付与機能" in reason
    assert atomic is False
