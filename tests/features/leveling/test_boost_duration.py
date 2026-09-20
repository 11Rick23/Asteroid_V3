from __future__ import annotations

from datetime import timedelta

import pytest

from app.features.leveling.domain.boost_duration import parse_boost_duration


@pytest.mark.parametrize(
    ("value", "seconds"),
    [("1s", 1), ("1m", 60), ("12h", 43200), ("1d", 86400), ("1w", 604800), ("1d12h", 129600), (" 1H 30m ", 5400)],
)
def test_parses_duration(value, seconds):
    """週・日・時・分・秒と組み合わせた期間を秒数に変換する。"""
    # 機能要件：コマンドで案内する単位と複合形式を受け付ける。
    # Given / When / Then
    assert parse_boost_duration(value) == timedelta(seconds=seconds)


@pytest.mark.parametrize("value", ["", " ", "0s", "-1h", "1.5h", "200", "1h?", "x1d", "1h-1m", "9" * 5000 + "d"])
def test_rejects_duration(value):
    """入力の一部だけを解釈せず、不正な期間全体を拒否する。"""
    # 機能要件：正の整数と対応単位からなる期間だけを受け付ける。
    # Given / When / Then
    assert parse_boost_duration(value) is None
