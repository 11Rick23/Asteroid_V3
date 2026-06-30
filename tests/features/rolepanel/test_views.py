from __future__ import annotations

from typing import Any, cast

import pytest

from app.features.rolepanel.admin_views import RolePanelAdminRoleSelect
from tests.support.discord_fakes import FakeInteraction, FakeUser


class _Response:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []
        self.deferred = False

    async def send_message(self, **kwargs: object) -> None:
        self.sent_messages.append(kwargs)

    async def defer(self, **_: object) -> None:
        self.deferred = True


@pytest.mark.asyncio
async def test_admin_role_select_rejects_unrelated_actor():
    """ロールパネル編集 UI は開始者でも管理者でもないユーザーの操作を拒否する。"""
    # 非機能要件：ロールパネル編集 UI は開始者または管理者以外の操作を拒否する。
    # 非機能要件：拒否された操作では DB 更新や panel refresh を実行しない。
    # Given
    refreshed = False

    async def on_update() -> None:
        nonlocal refreshed
        refreshed = True

    response = _Response()
    interaction = FakeInteraction(
        client=object(),
        guild_id=12345,
        channel_id=10,
        user=FakeUser(999),
        response=cast(Any, response),
    )
    select = RolePanelAdminRoleSelect(
        category_id=1,
        role_ids=[],
        actor_id=100,
        on_update=on_update,
    )

    # When
    await select.callback(cast(Any, interaction))

    # Then
    assert len(response.sent_messages) == 1
    assert response.sent_messages[0]["ephemeral"] is True
    assert response.deferred is False
    assert refreshed is False
