from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

import pytest

from app.features.bump_notifier.cog import BumpNotifier


class _Bot:
    def __init__(self, *, operating: bool = True) -> None:
        self.operating = operating
        self.remembered_messages: list[object] = []

    def is_operating_guild(self, _guild: object) -> bool:
        return self.operating

    def remember_message(self, message: object) -> None:
        self.remembered_messages.append(message)


class _Message:
    guild = object()


def test_initializes_notice_state():
    """BUMP / UP 通知時刻は Cog 作成時に未通知状態で初期化する。"""
    # 機能要件：BUMP / UP 通知は Cog 作成時に未通知状態から開始する。
    # 非機能要件：通知可能になるまでの待機時間はサービスごとの固定値で初期化される。
    # Given / When
    cog = BumpNotifier(cast(Any, object()))

    # Then
    assert cog.last_bump_notice_dt is None
    assert cog.last_dissoku_up_notice_dt is None
    assert cog.last_dicoall_up_notice_dt is None
    assert cog.BUMP_AVAILABLE_DELTA == timedelta(hours=2)
    assert cog.DISSOKU_UP_AVAILABLE_DELTA == timedelta(hours=2)
    assert cog.DICOALL_UP_AVAILABLE_DELTA == timedelta(hours=1)


@pytest.mark.asyncio
async def test_skips_outside_guild():
    """対象外 guild の message では通知状態やメッセージキャッシュを更新しない。"""
    # 非機能要件：対象外 guild の BUMP / UP 検知ではメッセージキャッシュを更新しない。
    # Given
    bot = _Bot(operating=False)
    cog = BumpNotifier(cast(Any, bot))

    # When
    await cog.on_message(cast(Any, _Message()))

    # Then
    assert bot.remembered_messages == []
