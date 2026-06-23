from __future__ import annotations

from typing import Any, cast

import pytest
from discord import Interaction

from app.core.bot import AsteroidBot
from app.features.auth.views import AuthButton, AuthChallengeView
from tests.support.discord_fakes import FakeClient, FakeInteraction, FakeUser


def test_builds_auth_button(operating_guild_id):
    """認証パネル用 View は永続化できる認証開始ボタンを含む。"""
    # Given / When
    view = AuthButton(cast(AsteroidBot, FakeClient(operating_guild_id)), timeout=None)

    # Then
    assert view.timeout is None
    assert len(view.children) == 1


@pytest.mark.asyncio
async def test_rejects_other_user(operating_guild_id):
    """認証チャレンジは開始した本人以外の操作を拒否し、ephemeral 通知を返す。"""
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
    assert interaction.response.sent_messages == [
        {"content": "この認証画面はあなた専用です。", "ephemeral": True},
    ]
