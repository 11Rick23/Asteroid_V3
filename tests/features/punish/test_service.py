from __future__ import annotations

import logging
from typing import Any, cast

import pytest

from app.features.punish import service
from tests.support.discord_fakes import FakeGuild, FakeInteraction, FakeMember, FakeRole, FakeUser


class _PunishConfig:
    crime_record_role_id_list = [10, 20]


class _Config:
    punish = _PunishConfig()


class _Bot:
    config = _Config()


class _CrimeRole(FakeRole):
    __slots__ = ("name",)

    def __init__(self, *, role_id: int, name: str) -> None:
        super().__init__(id=role_id, position=1)
        self.name = name


class _CrimeGuild(FakeGuild):
    def __init__(self, *, member: FakeMember, roles: list[FakeRole]) -> None:
        super().__init__()
        self.member = member
        self.roles_by_id = {role.id: role for role in roles}

    def get_member(self, user_id: int) -> FakeMember | None:
        return self.member if self.member.id == user_id else None

    def get_role(self, role_id: int) -> FakeRole | None:
        return self.roles_by_id.get(role_id)


def test_generates_reason(monkeypatch):
    """処罰理由には実行時刻と moderator 名を含める。"""
    # 機能要件：処罰理由には実行時刻と moderator 名を含める。
    # Given
    guild = FakeGuild()
    moderator = FakeMember(member_id=1, guild=guild, name="moderator")
    monkeypatch.setattr(service, "generate_timestamp", lambda: "2026/06/23 12:00:00")

    # When
    reason = service.generate_reason(cast(Any, moderator))

    # Then
    assert reason == "[2026/06/23 12:00:00] moderator によって処罰が行われました。"


def test_logs_action(caplog):
    """処罰操作ログには action、guild、moderator、target を含める。"""
    # 非機能要件：処罰操作ログには監査に必要な action、guild、moderator、target を記録する。
    # Given
    interaction = FakeInteraction(
        client=object(),
        guild_id=123,
        user=FakeUser(10),
    )
    interaction.guild = type("FakeGuild", (), {"id": 123})()

    # When
    with caplog.at_level(logging.INFO):
        service.log_punishment_action("ban", cast(Any, interaction), target_id=20, probation="なし")

    # Then
    assert "action=ban" in caplog.text
    assert "guild_id=123" in caplog.text
    assert "moderator_id=10" in caplog.text
    assert "target_id=20" in caplog.text


@pytest.mark.asyncio
async def test_gives_next_crime_role():
    """前科ロールは現在の前科数に応じた次のロールを付与する。"""
    # 機能要件：処罰時は対象者の現在の前科数に応じて次の前科ロールを付与する。
    # Given
    existing_crime_role = _CrimeRole(role_id=10, name="前科1")
    next_crime_role = _CrimeRole(role_id=20, name="前科2")
    target = FakeMember(guild=FakeGuild(), roles=[existing_crime_role])
    moderator = FakeMember(guild=FakeGuild(), name="moderator")
    guild = _CrimeGuild(member=target, roles=[existing_crime_role, next_crime_role])

    # When
    escaped = await service.give_crime_record_role(
        cast(Any, _Bot()),
        cast(Any, guild),
        cast(Any, target),
        cast(Any, moderator),
    )

    # Then
    assert escaped is False
    assert target.added_roles == [next_crime_role]


@pytest.mark.asyncio
async def test_skips_missing_target():
    """前科ロール付与対象が guild 内に見つからない場合は処理済みとして返す。"""
    # 非機能要件：対象 member が解決できない場合はロール付与を試みない。
    # Given
    guild = _CrimeGuild(member=FakeMember(member_id=999, guild=FakeGuild()), roles=[])
    target = FakeUser(100)
    moderator = FakeMember(guild=FakeGuild(), name="moderator")

    # When
    escaped = await service.give_crime_record_role(
        cast(Any, _Bot()),
        cast(Any, guild),
        cast(Any, target),
        cast(Any, moderator),
    )

    # Then
    assert escaped is True
