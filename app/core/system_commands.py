from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from app.common.command_groups import get_bot, register_command
from app.common.permissions import admin_only

if TYPE_CHECKING:
    from app.core.bot import AsteroidBot

logger = getLogger(__name__)


@app_commands.command(name="stop", description="BOTを安全に停止します。")
@app_commands.guild_only()
@admin_only
async def stop_bot(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    if bot.shutdown_requested:
        logger.warning(
            "BOT 停止コマンドを拒否しました: command=/stop reason=already_requested "
            f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id}"
        )
        await interaction.response.send_message("BOT は既に停止処理中です。", ephemeral=True)
        return

    logger.info(
        "BOT 停止コマンドを受け付けました: command=/stop "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id}"
    )
    try:
        await interaction.response.send_message("BOT の停止処理を開始します。", ephemeral=True)
    finally:
        bot.schedule_graceful_shutdown("command=/stop")


def register_system_commands(bot: AsteroidBot) -> None:
    register_command(bot, stop_bot)
