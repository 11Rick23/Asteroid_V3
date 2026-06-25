from __future__ import annotations

from typing import Any, cast

import pytest
from discord import Interaction

from app.core.bot import AsteroidBot
from app.features.auth import views
from app.features.auth.views import AuthButton, AuthChallengeView, complete_authentication
from tests.support.discord_fakes import FakeClient, FakeGuild, FakeInteraction, FakeMember, FakeRole, FakeUser


class _AuthConfig:
    unauthorized_role_id = 10


class _Config:
    auth = _AuthConfig()


class _Bot:
    config = _Config()


def test_builds_auth_button(operating_guild_id):
    """認証パネル用 View は永続化できる認証開始ボタンを含む。"""
    # 機能要件：認証パネルは認証開始用の永続ボタンを表示する。
    # Given / When
    view = AuthButton(cast(AsteroidBot, FakeClient(operating_guild_id)), timeout=None)

    # Then
    assert view.timeout is None
    assert len(view.children) == 1


@pytest.mark.asyncio
async def test_rejects_other_user(operating_guild_id):
    """認証チャレンジは開始した本人以外の操作を拒否し、ephemeral 通知を返す。"""
    # 機能要件：認証チャレンジは開始した本人以外の操作に拒否通知を返す。
    # 非機能要件：本人以外の UI 操作を認証処理として進めない。
    # Given
    view = AuthChallengeView(cast(Any, FakeClient(operating_guild_id)), "12345", owner_id=1)
    interaction = FakeInteraction(
        client=FakeClient(operating_guild_id),
        guild_id=operating_guild_id,
        user=FakeUser(2),
    )

    # When
    allowed = await view.interaction_check(cast(Interaction, interaction))

    # Then
    assert allowed is False
    assert len(interaction.response.sent_messages) == 1
    assert interaction.response.sent_messages[0]["ephemeral"] is True


@pytest.mark.asyncio
async def test_completes_authentication(monkeypatch):
    """認証完了時は未認証ロールを外し、初回ウェルカムを送信する。"""
    # 機能要件：認証完了時は未認証ロールを削除し、初回ウェルカムを送信する。
    # Given
    welcomed_members: list[object] = []

    async def fake_send_first_welcome(member: object) -> None:
        welcomed_members.append(member)

    unauthorized_role = FakeRole(id=10, position=1)
    guild = FakeGuild(roles=[unauthorized_role])
    member = FakeMember(guild=guild)
    interaction = FakeInteraction(
        client=FakeClient(12345),
        guild_id=12345,
        guild=guild,
        user=cast(Any, member),
    )
    monkeypatch.setattr(views.discord, "Member", FakeMember)
    monkeypatch.setattr(views, "send_first_welcome", fake_send_first_welcome)

    # When
    completed = await complete_authentication(cast(Any, _Bot()), cast(Interaction, interaction))

    # Then
    assert completed is True
    assert member.removed_roles == [unauthorized_role]
    assert welcomed_members == [member]


@pytest.mark.asyncio
async def test_rejects_non_member_authentication(monkeypatch):
    """guild 外または member 以外の interaction では認証完了処理を行わない。"""
    # 非機能要件：guild や member が解決できない認証完了処理では副作用を発生させない。
    # Given
    welcomed_members: list[object] = []
    interaction = FakeInteraction(
        client=FakeClient(12345),
        guild_id=None,
        guild=None,
        user=FakeUser(1),
    )
    monkeypatch.setattr(views, "send_first_welcome", lambda member: welcomed_members.append(member))

    # When
    completed = await complete_authentication(cast(Any, _Bot()), cast(Interaction, interaction))

    # Then
    assert completed is False
    assert welcomed_members == []
