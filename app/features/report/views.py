from __future__ import annotations

import discord

from .service import build_resolved_report_embed


class ReportResolveView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="対応完了", custom_id="coped", style=discord.ButtonStyle.green, emoji="✅")
    async def resolve_report(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.message is None or not interaction.message.embeds:
            await interaction.response.send_message("レポート情報が見つかりませんでした。", ephemeral=True)
            return

        await interaction.response.edit_message(
            embed=build_resolved_report_embed(interaction.message.embeds[0], interaction.user),
            view=None,
        )
