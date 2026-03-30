from __future__ import annotations

from app.common.constants import AsteroidEmoji

ACTION_POWER_COMMAND_NAME = "AddActionPower"


def parse_action_power_command(content: str) -> tuple[int, int] | None:
    parts = content.split()
    if len(parts) != 3 or parts[0] != ACTION_POWER_COMMAND_NAME:
        return None
    try:
        user_id = int(parts[1])
        value = int(parts[2])
    except ValueError:
        return None
    if user_id <= 0 or value <= 0:
        return None
    return user_id, value


def build_accumulated_action_power_message(total_action_power: int) -> str:
    return f"蓄積アクションパワー: {AsteroidEmoji.ACTION_POWER} {total_action_power}"
