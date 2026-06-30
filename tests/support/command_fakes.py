from __future__ import annotations

from discord import app_commands


class FakeCommandTree:
    def __init__(self) -> None:
        self.commands: dict[str, app_commands.Command | app_commands.ContextMenu | app_commands.Group] = {}

    def get_command(self, name: str) -> app_commands.Command | app_commands.ContextMenu | app_commands.Group | None:
        return self.commands.get(name)

    def add_command(self, command: app_commands.Command | app_commands.ContextMenu | app_commands.Group) -> None:
        self.commands[command.name] = command


class FakeCommandBot:
    def __init__(self) -> None:
        self.tree = FakeCommandTree()
