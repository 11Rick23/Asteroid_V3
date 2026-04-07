from __future__ import annotations

from app.features.leveling.action_power import (
    build_accumulated_action_power_message,
    parse_action_power_command,
)


def test_parse_action_power_command_returns_user_id_and_value() -> None:
    assert parse_action_power_command("AddActionPower 123456789 42") == (123456789, 42)
    assert parse_action_power_command("AddActionPower 123456789 42 Some reason") == (123456789, 42)


def test_parse_action_power_command_rejects_invalid_messages() -> None:
    assert parse_action_power_command("AddActionPower 123456789") is None
    assert parse_action_power_command("AddActionPower abc 42") is None
    assert parse_action_power_command("AddActionPower 123456789 0") is None
    assert parse_action_power_command("addactionpower 123456789 42") is None


def test_build_accumulated_action_power_message_formats_total() -> None:
    assert build_accumulated_action_power_message(1200) == "蓄積アクションパワー: <:_:1488099100518776993> 1200"
