from __future__ import annotations

import discord

from app.common.discord_types import as_messageable
from app.core.bot import AsteroidBot

from .service import apply_voice_xp_claim_side_effects, build_voice_xp_claim_message, claim_voice_xp_rewards


class ClaimVoiceXP(discord.ui.View):
    def __init__(self, bot: AsteroidBot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="VC経験値を獲得する", style=discord.ButtonStyle.success, custom_id="claim_voice_xp")
    async def button_callback(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        claim_result = await claim_voice_xp_rewards(self.bot, interaction.user.id)
        if claim_result is None:
            await interaction.response.send_message("VC経験値を獲得していません", ephemeral=True)
            return
        await interaction.response.send_message(content=build_voice_xp_claim_message(interaction.user, claim_result))
        await apply_voice_xp_claim_side_effects(
            self.bot,
            as_messageable(interaction.channel),
            interaction.user,
            claim_result,
        )
