from __future__ import annotations

from app.common.utils import humanize_number


def test_humanizes_number():
    """大きな数値は読みやすい K/M/B/T/Q 表記へ丸める。"""
    # 機能要件：大きな数値は表示用の短い単位表記へ変換する。
    # Given / When / Then
    assert humanize_number(999) == "999"
    assert humanize_number(1_500) == "1.5K"
    assert humanize_number(150_000) == "150K"
    assert humanize_number(1_500_000) == "1.5M"
    assert humanize_number(1_500_000_000) == "1.5B"
    assert humanize_number(1_500_000_000_000) == "1.5T"
    assert humanize_number(1_500_000_000_000_000) == "1Q"
