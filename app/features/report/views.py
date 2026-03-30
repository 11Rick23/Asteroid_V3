from __future__ import annotations

from logging import getLogger

import discord

from .service import build_resolved_report_embed

logger = getLogger(__name__)


class ReportResolveView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="対応完了", custom_id="coped", style=discord.ButtonStyle.green, emoji="✅")
    async def resolve_report(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if interaction.message is None or not interaction.message.embeds:
            logger.warning(
                f"レポート解決操作に失敗しました: message_id={getattr(interaction.message, 'id', None)} "
                f"user_id={interaction.user.id}"
            )
            await interaction.response.send_message("レポート情報が見つかりませんでした。", ephemeral=True)
            return

        await interaction.response.edit_message(
            embed=build_resolved_report_embed(interaction.message.embeds[0], interaction.user),
            view=None,
        )
        logger.info(f"レポートを対応完了にしました: message_id={interaction.message.id} user_id={interaction.user.id}")
