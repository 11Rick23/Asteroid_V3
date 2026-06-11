from __future__ import annotations

from typing import Any, cast

from discord import app_commands

from app.common.command_groups import (
    SETUP_GROUP_NAME,
    get_or_create_setup_group,
    register_command,
    register_setup_command,
)
from app.core.bot import AsteroidBot
from app.core.system_commands import register_system_commands, stop_bot
from app.features.auth import cog as auth_cog
from app.features.free_category import cog as free_category_cog


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


def module_command_names(module: object) -> set[str]:
    return {
        value.name
        for value in vars(module).values()
        if isinstance(value, (app_commands.Command, app_commands.Group))
    }


def test_register_command_is_idempotent() -> None:
    fake_bot = FakeBot()
    bot = cast(AsteroidBot, fake_bot)

    register_command(bot, ping_command)
    register_command(bot, ping_command)

    assert fake_bot.tree.get_command("ping") is ping_command
    assert fake_bot.tree.add_count == 1


def test_register_setup_command_creates_single_setup_group() -> None:
    fake_bot = FakeBot()
    bot = cast(AsteroidBot, fake_bot)

    register_setup_command(bot, setup_ping_command)
    register_setup_command(bot, setup_ping_command)

    setup_group = get_or_create_setup_group(bot)
    assert setup_group.name == SETUP_GROUP_NAME
    assert fake_bot.tree.get_command(SETUP_GROUP_NAME) is setup_group
    assert setup_group.get_command("setup_ping") is setup_ping_command
    assert len(list(setup_group.walk_commands())) == 1
    assert fake_bot.tree.add_count == 1


def test_register_system_commands_is_idempotent() -> None:
    fake_bot = FakeBot()
    bot = cast(AsteroidBot, fake_bot)

    register_system_commands(bot)
    register_system_commands(bot)

    assert fake_bot.tree.get_command("stop") is stop_bot
    assert fake_bot.tree.add_count == 1


def test_legacy_auth_and_free_category_setup_commands_are_removed() -> None:
    assert "auth" not in module_command_names(auth_cog)
    assert "free_category_button" not in module_command_names(free_category_cog)
