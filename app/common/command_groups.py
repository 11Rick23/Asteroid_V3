from __future__ import annotations

from typing import cast

import discord
from discord import app_commands

from app.core.bot import AsteroidBot

SETUP_GROUP_NAME = "setup"
SETUP_GROUP_DESCRIPTION = "セットアップ用のコマンドです。"


def get_bot(interaction: discord.Interaction) -> AsteroidBot:
    return cast(AsteroidBot, interaction.client)


def register_command(bot: AsteroidBot, command: app_commands.Command | app_commands.ContextMenu) -> None:
    if bot.tree.get_command(command.name) is None:
        bot.tree.add_command(command)


def register_group(bot: AsteroidBot, group: app_commands.Group) -> None:
    if bot.tree.get_command(group.name) is None:
        bot.tree.add_command(group)


def get_or_create_setup_group(bot: AsteroidBot) -> app_commands.Group:
    existing = bot.tree.get_command(SETUP_GROUP_NAME)
    if existing is None:
        group = app_commands.Group(name=SETUP_GROUP_NAME, description=SETUP_GROUP_DESCRIPTION)
        bot.tree.add_command(group)
        return group
    if not isinstance(existing, app_commands.Group):
        raise RuntimeError(f"`{SETUP_GROUP_NAME}` は Group ではありません。")
    return existing


def register_setup_command(bot: AsteroidBot, command: app_commands.Command) -> None:
    setup_group = get_or_create_setup_group(bot)
    if setup_group.get_command(command.name) is None:
        setup_group.add_command(command)
