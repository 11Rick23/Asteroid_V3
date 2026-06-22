from __future__ import annotations

import discord

from app.common.discord_types import as_messageable
from app.common.guild_scope import GuildScopedLayoutView
from app.core.bot import AsteroidBot

from .service import apply_voice_xp_claim_side_effects, build_voice_xp_claim_message, claim_voice_xp_rewards


class ClaimVoiceXPButton(discord.ui.Button["ClaimVoiceXP"]):
    def __init__(self, bot: AsteroidBot) -> None:
        super().__init__(
            label="VC経験値を獲得する",
            style=discord.ButtonStyle.success,
            custom_id="claim_voice_xp",
        )
        self.bot = bot

    async def callback(self, interaction: discord.Interaction) -> None:
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


class ClaimVoiceXP(GuildScopedLayoutView):
    def __init__(
        self,
        bot: AsteroidBot,
        *,
        title: str = "VC経験値獲得はこちら",
        description: str = "ボタンを押すとVC経験値を獲得します",
    ) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(f"# {title}\n{description}"),
                discord.ui.ActionRow(ClaimVoiceXPButton(bot)),
                accent_color=discord.Color.from_rgb(178, 177, 181),
            )
        )
