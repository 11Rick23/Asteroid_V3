from __future__ import annotations

import pytest


@pytest.fixture
def operating_guild_id() -> int:
    """テストで使う運用対象 guild ID を返す。"""
    return 12345
