from __future__ import annotations

from logging import getLogger

import discord
from discord import app_commands

from app.common.command_groups import get_bot
from app.common.discord_types import as_messageable
from app.common.permissions import admin_only

from .messages import voice_xp as voice_xp_messages
from .views import ClaimVoiceXP

logger = getLogger(__name__)


@app_commands.command(name="claim_voice_xp_button", description=voice_xp_messages.SETUP_VOICE_XP_DESCRIPTION)
@app_commands.guild_only()
@admin_only
async def claim_voice_xp_button(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    channel = as_messageable(interaction.channel)
    if channel is None:
        await interaction.response.send_message(voice_xp_messages.CHANNEL_NOT_MESSAGEABLE, ephemeral=True)
        return
    await channel.send(view=ClaimVoiceXP(bot))
    logger.info(
        "VC経験値獲得ボタンを設置しました: command=/setup claim_voice_xp_button "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id}"
    )
    await interaction.response.send_message(voice_xp_messages.VOICE_XP_BUTTON_INSTALLED, ephemeral=True)
