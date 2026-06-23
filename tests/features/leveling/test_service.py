from __future__ import annotations

from datetime import datetime

from app.database.repositories.monthly_powers import MonthlyPowerData
from app.features.leveling.build_send_message import format_prestige_num, format_ranking_position, total_monthly_power


def test_totals_monthly_power():
    """月間パワー合計は text、voice、action の合算で返す。"""
    # Given
    now = datetime(2026, 6, 23)
    monthly_power = MonthlyPowerData(
        user_id=1,
        text_power=10,
        voice_power=20,
        action_power=30,
        created_at=now,
        updated_at=now,
    )

    # When / Then
    assert total_monthly_power(monthly_power) == 60


def test_formats_rank():
    """ランキング表示は上位 3 件をメダル、それ以外を N位 で返す。"""
    # Given / When / Then
    assert format_ranking_position(1) == "🥇"
    assert format_ranking_position(2) == "🥈"
    assert format_ranking_position(3) == "🥉"
    assert format_ranking_position(4) == "4位"


def test_formats_prestige():
    """prestige 表示は 0 をハイフン、それ以外をローマ数字へ変換する。"""
    # Given / When / Then
    assert format_prestige_num(0) == "-"
    assert format_prestige_num(4) == "IV"
    assert format_prestige_num(9) == "IX"
    assert format_prestige_num(12) == "XII"
