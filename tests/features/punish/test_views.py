from __future__ import annotations

from typing import Any, cast

import discord
import pytest

from app.features.punish import views
from app.features.punish.views import PermRoleSelect
from tests.support.discord_fakes import FakeGuild, FakeInteraction, FakeMember, FakeUser


class _Response:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []

    async def send_message(self, content: str | None = None, **kwargs: object) -> None:
        self.sent_messages.append({"content": content, **kwargs})


@pytest.mark.asyncio
async def test_rejects_unrelated_actor(monkeypatch):
    """処罰を開始した moderator でも管理者でもないユーザーは権限剥奪 UI を実行できない。"""
    # 非機能要件：権限剥奪 UI は実行者本人または管理者以外の操作を拒否する。
    # 非機能要件：拒否された操作ではロール剥奪や処罰記録の副作用を発生させない。
    # Given
    guild = FakeGuild()
    target = FakeMember(member_id=200, guild=guild)
    response = _Response()
    interaction = FakeInteraction(
        client=object(),
        guild_id=guild.id,
        guild=guild,
        user=FakeUser(999),
        response=cast(Any, response),
    )
    select = PermRoleSelect(
        bot=cast(Any, object()),
        target=cast(Any, target),
        select_options=[discord.SelectOption(label="role", value="1")],
        reason="reason",
        probation=None,
        moderator_id=100,
    )
    monkeypatch.setattr(views, "is_administrator", lambda _user: False)

    # When
    await select.callback(cast(Any, interaction))

    # Then
    assert len(response.sent_messages) == 1
    assert response.sent_messages[0]["ephemeral"] is True
    assert target.removed_roles == []
