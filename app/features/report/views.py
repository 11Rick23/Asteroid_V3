from __future__ import annotations

from logging import getLogger

import discord

from app.common.guild_scope import GuildScopedView
from app.common.permissions import is_administrator

from .service import build_resolved_report_embed

logger = getLogger(__name__)


class ReportResolveView(GuildScopedView):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="対応完了", custom_id="coped", style=discord.ButtonStyle.green, emoji="✅")
    async def resolve_report(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not is_administrator(interaction.user):
            logger.debug(f"レポート解決操作を拒否しました: user_id={interaction.user.id}")
            await interaction.response.send_message("この操作を実行する権限がありません。", ephemeral=True)
            return

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
        logger.info(
            "レポートを対応完了にしました: action=report_resolve "
            f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
            f"actor_id={interaction.user.id} message_id={interaction.message.id}"
        )
