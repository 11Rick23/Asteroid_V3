from __future__ import annotations

from collections.abc import Iterable

from discord import app_commands

from app.common.command_groups import get_or_create_setup_group, register_setup_command
from app.core.system_commands import stop_bot
from app.features.auth.cog import setup_auth
from app.features.birthday.cog import birthday_set_others
from app.features.free_category.cog import free_category_button
from app.features.leveling.cog import claim_voice_xp_button
from app.features.leveling.commands.admin_command import leveling_admin_group
from app.features.leveling.commands.command import transfer_mee6
from app.features.punish.cog import punish_group
from app.features.rolepanel.cog import rolepanel_group
from app.features.starboard.cog import setup_starboard
from app.features.suggest.cog import suggest_group


class FakeTree:
    def __init__(self) -> None:
        self.commands: dict[str, object] = {}

    def get_command(self, name: str) -> object | None:
        return self.commands.get(name)

    def add_command(self, command: object) -> None:
        self.commands[command.name] = command


class FakeBot:
    def __init__(self) -> None:
        self.tree = FakeTree()


def concrete_commands(group: app_commands.Group) -> Iterable[app_commands.Command]:
    return (command for command in group.walk_commands() if isinstance(command, app_commands.Command))


def assert_admin_group(group: app_commands.Group) -> None:
    assert group.guild_only is True
    assert group.default_permissions is not None
    assert group.default_permissions.administrator is True

    commands = list(concrete_commands(group))
    assert commands
    for command in commands:
        assert command.default_permissions is not None
        assert command.default_permissions.administrator is True
        assert command.checks


def test_admin_groups_are_hidden_and_runtime_checked() -> None:
    assert_admin_group(leveling_admin_group)
    assert_admin_group(punish_group)
    assert_admin_group(rolepanel_group)
    assert_admin_group(suggest_group)


def test_stop_command_is_admin_only() -> None:
    assert stop_bot.guild_only is True
    assert stop_bot.default_permissions is not None
    assert stop_bot.default_permissions.administrator is True
    assert stop_bot.checks


def test_setup_group_and_setup_commands_are_admin_only() -> None:
    bot = FakeBot()

    for command in [setup_auth, free_category_button, claim_voice_xp_button, setup_starboard, transfer_mee6]:
        register_setup_command(bot, command)

    setup_group = get_or_create_setup_group(bot)
    assert_admin_group(setup_group)


def test_mixed_public_groups_keep_admin_subcommands_runtime_checked() -> None:
    assert birthday_set_others.checks
