from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from app.core.bot import AsteroidBot


class Error(commands.Cog):
    def __init__(self, bot: AsteroidBot):
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.tree.on_error = self.on_app_command_error

    async def on_app_command_error(
        self, interaction: discord.Interaction, exception: app_commands.AppCommandError
    ) -> None:
        log_channel_id = self.bot.config.get("main_log_channel_id")
        log_channel = self.bot.get_channel(log_channel_id) if log_channel_id else None
        if log_channel is not None:
            await log_channel.send(f"エラー！\n```python\n{exception}```")

        message = f"エラー！\n```python\n{exception}```"

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
