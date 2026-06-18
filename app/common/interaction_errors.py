from __future__ import annotations

from logging import getLogger

import discord

from app.common.constants import AsteroidColor
from app.common.error_reporting import send_exception_report

logger = getLogger(__name__)

DEFAULT_ERROR_MESSAGE = "コマンドの実行中にエラーが発生しました。"
UI_ERROR_MESSAGE = "操作中にエラーが発生しました。"
RATE_LIMITED_ERROR_MESSAGE = (
    "Discordのレート制限により処理を実行できませんでした。`{retry_after}秒後`に再試行してください。"
)


def build_error_embed(message: str) -> discord.Embed:
    return discord.Embed(title="エラー", description=message, color=AsteroidColor.WARNING)


def format_rate_limited_error(retry_after: float, *, action: str = "処理を実行できませんでした。") -> str:
    return f"Discordのレート制限により{action}`{round(retry_after, 1)}秒後`に再試行してください。"


async def send_error_embed(
    interaction: discord.Interaction,
    message: str,
    *,
    ephemeral: bool = True,
) -> None:
    embeds = [build_error_embed(message)]
    if interaction.response.is_done():
        await interaction.followup.send(embeds=embeds, ephemeral=ephemeral)
        return
    await interaction.response.send_message(embeds=embeds, ephemeral=ephemeral)


async def send_rate_limited_error(
    interaction: discord.Interaction,
    retry_after: float,
    *,
    log_prefix: str,
) -> None:
    rounded_retry_after = round(retry_after, 1)
    command = getattr(interaction, "command", None)
    command_name = getattr(command, "qualified_name", None)
    command_fragment = f": {command_name}" if command_name else ""
    user = getattr(interaction, "user", None)
    user_id = getattr(user, "id", "unknown")
    logger.warning(
        f"{log_prefix}{command_fragment} guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"user_id={user_id} retry_after={rounded_retry_after}"
    )
    await send_error_embed(
        interaction,
        RATE_LIMITED_ERROR_MESSAGE.format(retry_after=rounded_retry_after),
    )


async def handle_ui_error(interaction: discord.Interaction, error: Exception) -> None:
    if isinstance(error, discord.RateLimited):
        await send_rate_limited_error(
            interaction,
            error.retry_after,
            log_prefix="UI interaction rate limited",
        )
        return

    user = getattr(interaction, "user", None)
    user_id = getattr(user, "id", "unknown")
    logger.exception(
        f"UI interaction failed: guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"user_id={user_id}",
        exc_info=(type(error), error, error.__traceback__),
    )
    await send_exception_report(
        interaction.client,
        title="UI操作エラー",
        exception=error,
        fields=(
            ("ユーザー", f"`{user_id}`"),
            ("サーバー / チャンネル", f"`{interaction.guild_id or 'DM'}` / `{interaction.channel_id or 'unknown'}`"),
        ),
    )
    await send_error_embed(interaction, UI_ERROR_MESSAGE)
