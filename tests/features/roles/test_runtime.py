from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import pytest

from app.database.repositories.user_roles import UserRoleData
from app.features.roles import cog as roles_cog
from app.features.roles.cog import JoinRolesCog
from tests.support.discord_fakes import FakeGuild, FakeMember, FakeRole


class _RolesConfig:
    join_role_id_list = [10, 20, 999]
    bot_join_role_id_list = [30]


class _Config:
    roles = _RolesConfig()


class _UserRolesRepository:
    def __init__(self, *, restore_count: int = 0) -> None:
        self.restore_count = restore_count
        self.saved_roles: list[tuple[int, list[int]]] = []
        self.deleted_roles: list[tuple[int, int]] = []

    async def save_user_roles(self, user_id: int, role_ids: list[int]) -> None:
        self.saved_roles.append((user_id, role_ids))

    async def get_user_roles(self, user_id: int) -> list[UserRoleData]:
        now = datetime.now()
        return [
            UserRoleData(user_id=user_id, role_id=10 + index, created_at=now, updated_at=now)
            for index in range(self.restore_count)
        ]

    async def delete_user_role(self, user_id: int, role_id: int) -> None:
        self.deleted_roles.append((user_id, role_id))


class _Database:
    def __init__(self, user_roles: _UserRolesRepository) -> None:
        self.user_roles = user_roles


class _Bot:
    config = _Config()

    def __init__(self, *, operating: bool = True, restore_count: int = 0) -> None:
        self.operating = operating
        self.user_roles = _UserRolesRepository(restore_count=restore_count)
        self.db = _Database(self.user_roles)

    def is_operating_guild(self, _guild: object) -> bool:
        return self.operating


@pytest.mark.asyncio
async def test_skips_outside_guild():
    """対象外 guild の脱退イベントではロール保存を行わない。"""
    # 非機能要件：対象外 guild の member remove では DB 更新を行わない。
    # Given
    bot = _Bot(operating=False)
    cog = JoinRolesCog(cast(Any, bot))
    member = FakeMember(guild=FakeGuild())

    # When
    await cog.save_roles(cast(Any, member))

    # Then
    assert bot.user_roles.saved_roles == []


@pytest.mark.asyncio
async def test_gives_join_roles():
    """復元対象がない参加者には設定済みの参加時ロールだけを付与する。"""
    # 機能要件：復元ロールがない通常ユーザーには設定済みの参加時ロールを付与する。
    # 非機能要件：存在しないロールや BOT が管理できないロールは付与しない。
    # Given
    low_role = FakeRole(id=10, position=10)
    high_role = FakeRole(id=20, position=1000)
    guild = FakeGuild(roles=[low_role, high_role], bot_top_role=FakeRole(id=999, position=100))
    member = FakeMember(guild=guild)
    cog = JoinRolesCog(cast(Any, _Bot()))

    # When
    await cog.restore_or_give_roles(cast(Any, member))

    # Then
    assert member.added_roles == [low_role]


@pytest.mark.asyncio
async def test_sends_return_welcome(monkeypatch):
    """ロール復元が行われた再参加者には帰還ウェルカムを送信する。"""
    # 機能要件：ロール復元済みの再参加ユーザーには帰還ウェルカムを送信する。
    # 非機能要件：復元済みユーザーには参加時ロールを追加付与しない。
    # Given
    welcomed_members: list[object] = []

    async def fake_send_return_welcome(member: object) -> None:
        welcomed_members.append(member)

    monkeypatch.setattr(roles_cog, "send_return_welcome", fake_send_return_welcome)
    bot = _Bot(restore_count=2)
    cog = JoinRolesCog(cast(Any, bot))
    restored_role = FakeRole(id=10, position=10)
    member = FakeMember(guild=FakeGuild(roles=[restored_role]))

    # When
    await cog.restore_or_give_roles(cast(Any, member))

    # Then
    assert welcomed_members == [member]
    assert member.added_roles == [restored_role]
