from __future__ import annotations

import traceback
from logging import getLogger

import discord
from discord import app_commands
from discord.ext import commands

from app.common.constants import AsteroidColor
from app.common.discord_types import as_messageable
from app.common.guild_scope import OutsideOperatingGuild, send_outside_operating_guild_message
from app.core.bot import AsteroidBot

logger = getLogger(__name__)
TRACEBACK_TAIL_LINES = 12
TRACEBACK_MAX_LENGTH = 1800
DEFAULT_ERROR_MESSAGE = "コマンドの実行中にエラーが発生しました。"


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


def build_error_embed(message: str) -> discord.Embed:
    return discord.Embed(title="エラー", description=message, color=AsteroidColor.WARNING)


def build_traceback_embed(traceback_tail: str) -> discord.Embed:
    return discord.Embed(
        title="トレースバック",
        description=f"```python\n{traceback_tail}\n```",
        color=AsteroidColor.DARK_EMBED_COLOR,
    )


def build_log_error_embed(interaction: discord.Interaction, exception: BaseException) -> discord.Embed:
    command_name = interaction.command.qualified_name if interaction.command is not None else "unknown"
    user_id = interaction.user.id if interaction.user is not None else "unknown"
    guild_id = interaction.guild_id or "DM"
    channel_id = interaction.channel_id or "unknown"
    embed = discord.Embed(
        title="アプリコマンドエラー",
        description=f"`{type(exception).__name__}`: {exception}",
        color=AsteroidColor.WARNING,
    )
    embed.add_field(name="コマンド", value=f"`{command_name}`", inline=False)
    embed.add_field(name="ユーザー", value=f"`{interaction.user}` (`{user_id}`)", inline=False)
    embed.add_field(name="サーバー / チャンネル", value=f"`{guild_id}` / `{channel_id}`", inline=False)
    return embed


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
        traceback_tail = build_traceback_tail(original)
        logger.exception(
            "App command failed: "
            f"{interaction.command.qualified_name if interaction.command is not None else 'unknown'}",
            exc_info=(type(original), original, original.__traceback__),
        )

        log_channel_id = self.bot.config.log.main_log_channel_id
        log_channel = as_messageable(self.bot.get_channel(log_channel_id)) if log_channel_id else None
        if log_channel is not None and self.bot.is_operating_channel(log_channel):
            await log_channel.send(
                embeds=[
                    build_log_error_embed(interaction, original),
                    build_traceback_embed(traceback_tail),
                ]
            )

        message = DEFAULT_ERROR_MESSAGE
        show_traceback = True

        if isinstance(exception, app_commands.MissingPermissions):
            message = "権限が足りません！"
            show_traceback = False
        elif isinstance(exception, app_commands.BotMissingPermissions):
            message = "コマンドを実行するのにBOTに必要な権限がありません！"
            show_traceback = False
        elif isinstance(exception, app_commands.CommandOnCooldown):
            message = f"コマンドはクールダウン中です！\n`{round(exception.retry_after, 2)}秒後`に再度試してください。"
            show_traceback = False
        elif isinstance(exception, app_commands.TransformerError):
            message = "渡された引数が無効です！"
            show_traceback = False
        elif isinstance(exception, app_commands.CheckFailure):
            message = "このコマンドを実行する権限がありません。"
            show_traceback = False

        embeds = [build_error_embed(message)]
        if show_traceback:
            embeds.append(build_traceback_embed(traceback_tail))

        if interaction.response.is_done():
            await interaction.followup.send(embeds=embeds, ephemeral=True)
        else:
            await interaction.response.send_message(embeds=embeds, ephemeral=True)


async def setup(bot: AsteroidBot) -> None:
    await bot.add_cog(Error(bot))
