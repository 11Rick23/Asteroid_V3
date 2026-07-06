from __future__ import annotations

from logging import getLogger

import discord

from app.common.permissions import is_administrator
from app.core.bot import AsteroidBot

from .service import generate_reason, give_crime_record_role, log_punishment_action, send_punish_message

logger = getLogger(__name__)


class PermRoleSelect(discord.ui.Select):
    def __init__(
        self,
        bot: AsteroidBot,
        target: discord.Member,
        select_options: list[discord.SelectOption],
        reason: str,
        probation: str | None,
        moderator_id: int | None = None,
    ):
        super().__init__(
            placeholder="剥奪する権限ロールを選択…",
            options=select_options,
            min_values=1,
            max_values=max(1, len(select_options)),
        )
        self.bot = bot
        self.target = target
        self.reason = reason
        self.probation = probation
        self.moderator_id = moderator_id

    async def callback(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if guild is None:
            logger.warning(f"権限剥奪UIをサーバー外で受信しました: target_id={getattr(self.target, 'id', None)}")
            await interaction.response.send_message("サーバー内でのみ使用できます。", ephemeral=True)
            return

        if (
            self.moderator_id is not None
            and interaction.user.id != self.moderator_id
            and not is_administrator(interaction.user)
        ):
            logger.debug(
                "権限剥奪UIの操作を拒否しました: "
                f"guild_id={guild.id} actor_id={interaction.user.id} moderator_id={self.moderator_id} "
                f"target_id={self.target.id}"
            )
            await interaction.response.send_message("この操作を実行する権限がありません。", ephemeral=True)
            return

        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("サーバー内でのみ使用できます。", ephemeral=True)
            return

        log_punishment_action("権限剥奪", interaction, self.target.id, probation=self.probation)
        await give_crime_record_role(self.bot, guild, self.target, interaction.user)
        roles = [role for value in self.values if (role := guild.get_role(int(value))) is not None]
        if self.probation is None and roles:
            await self.target.remove_roles(*roles, reason=generate_reason(interaction.user), atomic=False)

        punishment_board = guild.get_channel(self.bot.config.punish.punishment_board_channel_id)
        if not isinstance(punishment_board, discord.TextChannel):
            await interaction.response.send_message("処罰板チャンネルが見つかりません。", ephemeral=True)
            return
        await send_punish_message(
            punishment_board,
            self.target,
            self.reason,
            f"権限剥奪 {[role.name for role in roles]}",
            self.probation,
        )
        await interaction.response.edit_message(content="送信完了です！", view=None)
