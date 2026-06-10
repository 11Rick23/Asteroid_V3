from __future__ import annotations

from logging import getLogger

import discord
from discord import app_commands

from app.common.command_groups import get_bot
from app.common.constants import AsteroidColor
from app.common.discord_types import as_messageable
from app.common.permissions import admin_only

from .views import ClaimVoiceXP

logger = getLogger(__name__)


@app_commands.command(name="claim_voice_xp_button", description="VC経験値獲得用のボタンを設置します")
@app_commands.guild_only()
@admin_only
async def claim_voice_xp_button(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    channel = as_messageable(interaction.channel)
    if channel is None:
        await interaction.response.send_message("このチャンネルには送信できません。", ephemeral=True)
        return
    embed = discord.Embed(
        title="VC経験値獲得はこちら",
        description="ボタンを押すとVC経験値を獲得します",
        color=AsteroidColor.INFO,
    )
    await channel.send(embed=embed, view=ClaimVoiceXP(bot))
    logger.info(
        "VC経験値獲得ボタンを設置しました: command=/setup claim_voice_xp_button "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id}"
    )
    await interaction.response.send_message("VC経験値獲得用のボタンを設置しました！", ephemeral=True)
