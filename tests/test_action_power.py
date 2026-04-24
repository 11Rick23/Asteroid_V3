from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.features.leveling.action_power import (
    build_accumulated_action_power_message,
    parse_action_power_command,
)
from app.features.leveling.commands.admin_command import action_power_total


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


class FakeMonthlyActionPowers:
    async def sum_action_power(self) -> int:
        return 1200


class FakeResponse:
    def __init__(self) -> None:
        self.messages: list[tuple[str, bool]] = []

    async def send_message(self, content: str, *, ephemeral: bool = False) -> None:
        self.messages.append((content, ephemeral))


class FakeInteraction:
    def __init__(self) -> None:
        self.client = SimpleNamespace(
            db=SimpleNamespace(monthly_action_powers=FakeMonthlyActionPowers()),
        )
        self.guild_id = 123
        self.channel_id = 456
        self.user = SimpleNamespace(id=789)
        self.response = FakeResponse()


@pytest.mark.asyncio
async def test_action_power_total_sends_current_total_ephemerally() -> None:
    interaction = FakeInteraction()

    await action_power_total.callback(interaction)  # type: ignore[arg-type]

    assert interaction.response.messages == [
        ("蓄積アクションパワー: <:_:1488099100518776993> 1200", True),
    ]
