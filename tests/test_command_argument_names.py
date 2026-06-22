from __future__ import annotations

import re
from collections.abc import Iterable
from typing import cast

from discord import app_commands

from app.core.system_commands import stop_bot
from app.features.birthday.cog import birthday_group
from app.features.free_category.cog import free_category_group
from app.features.leveling.commands.admin_command import leveling_admin_group
from app.features.leveling.commands.command import rank, transfer_mee6
from app.features.punish.cog import punish_group
from app.features.report.cog import ReportCog
from app.features.rolepanel.commands import rolepanel_group
from app.features.suggest.cog import suggest_group
from app.features.vc.cog import vc_group

JAPANESE_CHARACTER = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def concrete_commands(group: app_commands.Group) -> Iterable[app_commands.Command]:
    return (command for command in group.walk_commands() if isinstance(command, app_commands.Command))


def test_public_command_argument_names_are_japanese() -> None:
    commands = [
        *concrete_commands(birthday_group),
        *concrete_commands(free_category_group),
        *concrete_commands(leveling_admin_group),
        *concrete_commands(punish_group),
        *concrete_commands(rolepanel_group),
        *concrete_commands(suggest_group),
        *concrete_commands(vc_group),
        rank,
        stop_bot,
        transfer_mee6,
        cast(app_commands.Command, ReportCog.report),
    ]

    english_arguments = [
        f"/{command.qualified_name} {parameter.display_name}"
        for command in commands
        for parameter in command.parameters
        if JAPANESE_CHARACTER.search(parameter.display_name) is None
    ]

    assert english_arguments == []


def test_rolepanel_category_description_arguments() -> None:
    commands = {command.qualified_name: command for command in concrete_commands(rolepanel_group)}

    add_parameters = {parameter.name: parameter for parameter in commands["rolepanel category add"].parameters}
    edit_parameters = {parameter.name: parameter for parameter in commands["rolepanel category edit"].parameters}

    assert add_parameters["description"].display_name == "説明文"
    assert add_parameters["description"].required is True
    assert edit_parameters["description"].display_name == "説明文"
    assert edit_parameters["description"].required is False
