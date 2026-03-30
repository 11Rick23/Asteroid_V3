from __future__ import annotations

from app.features.punish.cog import punish_group


def test_all_punish_commands_are_guild_only() -> None:
    commands = list(punish_group.walk_commands())

    assert commands
    assert all(command.guild_only is True for command in commands)
