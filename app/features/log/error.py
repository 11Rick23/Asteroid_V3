from __future__ import annotations

import traceback
from logging import getLogger

import discord
from discord import app_commands
from discord.ext import commands

from app.core.bot import AsteroidBot

logger = getLogger(__name__)
TRACEBACK_TAIL_LINES = 12
TRACEBACK_MAX_LENGTH = 1800


def unwrap_app_command_error(exception: app_commands.AppCommandError) -> Exception:
    if isinstance(exception, app_commands.CommandInvokeError):
        return exception.original
    return exception


def build_traceback_tail(exception: BaseException) -> str:
    lines = traceback.format_exception(type(exception), exception, exception.__traceback__)
    tail = "".join(lines[-TRACEBACK_TAIL_LINES:]).strip()
    if len(tail) > TRACEBACK_MAX_LENGTH:
        tail = "...\n" + tail[-TRACEBACK_MAX_LENGTH:]
    return tail


def build_log_message(interaction: discord.Interaction, exception: BaseException, traceback_tail: str) -> str:
    command_name = interaction.command.qualified_name if interaction.command is not None else "unknown"
    user_id = interaction.user.id if interaction.user is not None else "unknown"
    guild_id = interaction.guild_id or "DM"
    channel_id = interaction.channel_id or "unknown"
    return (
        "エラー！\n"
        f"command: `{command_name}`\n"
        f"user: `{interaction.user}` ({user_id})\n"
        f"guild: `{guild_id}` channel: `{channel_id}`\n"
        f"```python\n{traceback_tail}\n```"
    )


class Error(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.tree.on_error = self.on_app_command_error

    async def on_app_command_error(
        self, interaction: discord.Interaction, exception: app_commands.AppCommandError
    ) -> None:
        original = unwrap_app_command_error(exception)
        traceback_tail = build_traceback_tail(original)
        logger.exception(
            "App command failed: %s",
            interaction.command.qualified_name if interaction.command is not None else "unknown",
            exc_info=(type(original), original, original.__traceback__),
        )

        log_channel_id = self.bot.config.log.main_log_channel_id
        log_channel = self.bot.get_channel(log_channel_id) if log_channel_id else None
        if log_channel is not None:
            await log_channel.send(build_log_message(interaction, original, traceback_tail))

        message = f"エラー！\n```python\n{traceback_tail}\n```"

        if isinstance(exception, app_commands.MissingPermissions):
            message = "権限が足りません！"
        elif isinstance(exception, app_commands.BotMissingPermissions):
            message = "コマンドを実行するのにBOTに必要な権限がありません！"
        elif isinstance(exception, app_commands.CommandOnCooldown):
            message = f"コマンドはクールダウン中です！\n`{round(exception.retry_after, 2)}秒後`に再度試してください。"
        elif isinstance(exception, app_commands.TransformerError):
            message = "渡された引数が無効です！"
        elif isinstance(exception, app_commands.CheckFailure):
            message = "このコマンドを実行する権限がありません。"

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


async def setup(bot: AsteroidBot) -> None:
    await bot.add_cog(Error(bot))
