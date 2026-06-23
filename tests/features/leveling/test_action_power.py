from __future__ import annotations

from app.features.leveling.action_power import build_accumulated_action_power_message, parse_action_power_command


def test_parses_command():
    """AddActionPower コマンド文字列からユーザー ID と加算値を取り出す。"""
    # Given / When
    result = parse_action_power_command("AddActionPower 123 45 reason text")

    # Then
    assert result == (123, 45)


def test_rejects_invalid_command():
    """形式不正、非数値、0 以下の値は action power コマンドとして扱わない。"""
    # Given / When / Then
    assert parse_action_power_command("Other 123 45") is None
    assert parse_action_power_command("AddActionPower user 45") is None
    assert parse_action_power_command("AddActionPower 123 0") is None


def test_builds_message():
    """蓄積アクションパワー表示は合計値を含む定型文にする。"""
    # Given / When
    message = build_accumulated_action_power_message(120)

    # Then
    assert message.endswith(" 120")
    assert "蓄積アクションパワー" in message
