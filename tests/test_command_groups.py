from __future__ import annotations

from typing import Any

from discord import app_commands

from app.common.command_groups import (
    SETUP_GROUP_NAME,
    get_or_create_setup_group,
    register_command,
    register_setup_command,
)


class FakeTree:
    def __init__(self) -> None:
        self.commands: dict[str, Any] = {}
        self.add_count = 0

    def get_command(self, name: str) -> Any:
        return self.commands.get(name)

    def add_command(self, command: Any) -> None:
        self.add_count += 1
        self.commands[command.name] = command


class FakeBot:
    def __init__(self) -> None:
        self.tree = FakeTree()


@app_commands.command(name="ping", description="test")
async def ping_command(_: Any) -> None:
    return None


@app_commands.command(name="setup_ping", description="test")
async def setup_ping_command(_: Any) -> None:
    return None


def test_register_command_is_idempotent() -> None:
    bot = FakeBot()

    register_command(bot, ping_command)
    register_command(bot, ping_command)

    assert bot.tree.get_command("ping") is ping_command
    assert bot.tree.add_count == 1


def test_register_setup_command_creates_single_setup_group() -> None:
    bot = FakeBot()

    register_setup_command(bot, setup_ping_command)
    register_setup_command(bot, setup_ping_command)

    setup_group = get_or_create_setup_group(bot)
    assert setup_group.name == SETUP_GROUP_NAME
    assert bot.tree.get_command(SETUP_GROUP_NAME) is setup_group
    assert setup_group.get_command("setup_ping") is setup_ping_command
    assert len(list(setup_group.walk_commands())) == 1
    assert bot.tree.add_count == 1
