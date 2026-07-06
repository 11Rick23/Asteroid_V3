from __future__ import annotations

from logging import getLogger

import discord
from discord import app_commands
from discord.ext import commands

from app.common.error_reporting import (
    ErrorReportField,
    build_traceback_embed,
    build_traceback_tail,
    send_exception_report,
)
from app.common.guild_scope import OutsideOperatingGuild, send_outside_operating_guild_message
from app.common.interaction_errors import (
    DEFAULT_ERROR_MESSAGE,
    build_error_embed,
    send_error_embed,
    send_rate_limited_error,
)
from app.core.bot import AsteroidBot

logger = getLogger(__name__)


def unwrap_app_command_error(exception: app_commands.AppCommandError) -> Exception:
    if isinstance(exception, app_commands.CommandInvokeError):
        return exception.original
    return exception


def get_expected_app_command_error_message(exception: app_commands.AppCommandError) -> str | None:
    if isinstance(exception, app_commands.MissingPermissions):
        return "権限が足りません！"
    if isinstance(exception, app_commands.BotMissingPermissions):
        return "コマンドを実行するのにBOTに必要な権限がありません！"
    if isinstance(exception, app_commands.CommandOnCooldown):
        return f"コマンドはクールダウン中です！\n`{round(exception.retry_after, 2)}秒後`に再度試してください。"
    if isinstance(exception, app_commands.TransformerError):
        return "渡された引数が無効です！"
    if isinstance(exception, app_commands.CheckFailure):
        return "このコマンドを実行する権限がありません。"
    return None


def build_app_command_report_fields(interaction: discord.Interaction) -> tuple[ErrorReportField, ...]:
    command_name = interaction.command.qualified_name if interaction.command is not None else "unknown"
    user_id = interaction.user.id if interaction.user is not None else "unknown"
    guild_id = interaction.guild_id or "DM"
    channel_id = interaction.channel_id or "unknown"
    return (
        ("コマンド", f"`{command_name}`"),
        ("ユーザー", f"`{interaction.user}` (`{user_id}`)"),
        ("サーバー / チャンネル", f"`{guild_id}` / `{channel_id}`"),
    )


class Error(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.tree.on_error = self.on_app_command_error

    async def on_app_command_error(
        self, interaction: discord.Interaction, exception: app_commands.AppCommandError
    ) -> None:
        if isinstance(exception, OutsideOperatingGuild):
            logger.debug(
                f"稼働ギルド外のコマンド実行を拒否しました: guild_id={interaction.guild_id} "
                f"channel_id={interaction.channel_id} user_id={interaction.user.id}"
            )
            await send_outside_operating_guild_message(interaction)
            return

        original = unwrap_app_command_error(exception)
        if isinstance(original, discord.RateLimited):
            await send_rate_limited_error(interaction, original.retry_after, log_prefix="App command rate limited")
            return

        expected_message = get_expected_app_command_error_message(exception)
        if expected_message is None and isinstance(original, app_commands.AppCommandError):
            expected_message = get_expected_app_command_error_message(original)
        if expected_message is not None:
            await send_error_embed(interaction, expected_message)
            return

        traceback_tail = build_traceback_tail(original)
        logger.exception(
            "App command failed: "
            f"{interaction.command.qualified_name if interaction.command is not None else 'unknown'}",
            exc_info=(type(original), original, original.__traceback__),
        )
        await send_exception_report(
            self.bot,
            title="アプリコマンドエラー",
            exception=original,
            fields=build_app_command_report_fields(interaction),
        )

        message = DEFAULT_ERROR_MESSAGE
        embeds = [build_error_embed(message), build_traceback_embed(traceback_tail)]

        if interaction.response.is_done():
            await interaction.followup.send(embeds=embeds, ephemeral=True)
        else:
            await interaction.response.send_message(embeds=embeds, ephemeral=True)


async def setup(bot: AsteroidBot) -> None:
    await bot.add_cog(Error(bot))
