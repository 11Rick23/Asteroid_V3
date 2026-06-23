from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from app.features.bump_notifier.cog import BumpNotifier


def test_initializes_notice_state():
    """BUMP / UP 通知時刻は Cog 作成時に未通知状態で初期化する。"""
    # Given / When
    cog = BumpNotifier(cast(Any, object()))

    # Then
    assert cog.last_bump_notice_dt is None
    assert cog.last_dissoku_up_notice_dt is None
    assert cog.last_dicoall_up_notice_dt is None
    assert cog.BUMP_AVAILABLE_DELTA == timedelta(hours=2)
    assert cog.DISSOKU_UP_AVAILABLE_DELTA == timedelta(hours=2)
    assert cog.DICOALL_UP_AVAILABLE_DELTA == timedelta(hours=1)
