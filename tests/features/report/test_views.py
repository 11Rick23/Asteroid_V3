from __future__ import annotations

from typing import Any, cast

import pytest

from app.features.report import views
from app.features.report.views import ReportResolveView
from tests.support.discord_fakes import FakeInteraction, FakeUser


class _Response:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []
        self.edits: list[dict[str, object]] = []

    async def send_message(self, content: str | None = None, **kwargs: object) -> None:
        self.sent_messages.append({"content": content, **kwargs})

    async def edit_message(self, **kwargs: object) -> None:
        self.edits.append(kwargs)


@pytest.mark.asyncio
async def test_rejects_non_admin(monkeypatch):
    """管理者以外の対応完了操作は拒否し、通報 Embed を更新しない。"""
    # 非機能要件：管理者以外は通報の対応完了 UI を実行できない。
    # 非機能要件：拒否された操作では通報 Embed を更新しない。
    # Given
    view = ReportResolveView()
    response = _Response()
    interaction = FakeInteraction(
        client=object(),
        guild_id=12345,
        user=FakeUser(100),
        response=cast(Any, response),
    )
    monkeypatch.setattr(views, "is_administrator", lambda _user: False)

    # When
    await view.children[0].callback(cast(Any, interaction))

    # Then
    assert len(response.sent_messages) == 1
    assert response.sent_messages[0]["ephemeral"] is True
    assert response.edits == []
