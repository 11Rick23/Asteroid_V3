from __future__ import annotations

from logging import getLogger

import discord
from discord import app_commands

from app.common.command_groups import get_bot
from app.common.permissions import admin_only
from app.database.account_migration import PendingState
from app.features.leveling.commands.admin_groups import leveling_admin_group
from app.features.leveling.messages import restore as messages

logger = getLogger(__name__)
pending_group = app_commands.Group(name="pending", description=messages.PENDING_DESCRIPTION)


@pending_group.command(name="set", description=messages.PENDING_DESCRIPTION)
@app_commands.rename(
    user=messages.USER_LABEL,
    voice_shard="ボイスシャード",
    bonus_shard="ボーナスシャード",
    voice_power="ボイスパワー",
    half_notify="半分通知",
    full_notify="上限通知",
)
@app_commands.describe(
    user=messages.USER_DESCRIPTION,
    voice_shard=messages.AMOUNT_DESCRIPTION,
    bonus_shard=messages.AMOUNT_DESCRIPTION,
    voice_power=messages.AMOUNT_DESCRIPTION,
    half_notify=messages.HALF_DESCRIPTION,
    full_notify=messages.FULL_DESCRIPTION,
)
@admin_only
async def set_pending(
    interaction: discord.Interaction,
    user: discord.User,
    voice_shard: app_commands.Range[int, 0, 4294967295],
    bonus_shard: app_commands.Range[int, 0, 4294967295],
    voice_power: app_commands.Range[int, 0, 4294967295],
    half_notify: bool,
    full_notify: bool,
) -> None:
    values = PendingState(voice_shard, bonus_shard, voice_power, half_notify, full_notify)
    try:
        values.validate()
    except ValueError:
        await interaction.response.send_message(messages.POWER_RANGE_ERROR, ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    await get_bot(interaction).db.account_migration.set_pending(user.id, values)
    logger.info(
        "未受取XPを設定しました: command=/leveling pending set guild_id=%s actor_id=%s target_id=%s values=%s",
        interaction.guild_id,
        interaction.user.id,
        user.id,
        values,
    )
    await interaction.followup.send(messages.SET_COMPLETED, ephemeral=True)


def register_pending_command() -> None:
    if leveling_admin_group.get_command("pending") is None:
        leveling_admin_group.add_command(pending_group)
