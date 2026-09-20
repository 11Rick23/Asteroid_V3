from __future__ import annotations

from logging import getLogger

import discord
from discord import app_commands

from app.common.command_groups import get_bot
from app.common.permissions import admin_only
from app.database.leveling_state import PowerState, ShardState
from app.features.leveling.commands.admin_groups import admin_power_group, admin_shard_group
from app.features.leveling.commands.pending_command import register_pending_command
from app.features.leveling.manage_reward_role import sync_grade_prestige_role
from app.features.leveling.messages import restore as messages

logger = getLogger(__name__)


@app_commands.command(name="set", description=messages.SHARD_SET_DESCRIPTION)
@app_commands.rename(
    user=messages.USER_LABEL, text=messages.TEXT_LABEL, voice=messages.VOICE_LABEL, bonus=messages.BONUS_LABEL
)
@app_commands.describe(
    user=messages.USER_DESCRIPTION,
    text=messages.AMOUNT_DESCRIPTION,
    voice=messages.AMOUNT_DESCRIPTION,
    bonus=messages.AMOUNT_DESCRIPTION,
)
@admin_only
async def set_shards(
    interaction: discord.Interaction,
    user: discord.User,
    text: app_commands.Range[int, 0, 68703999],
    voice: app_commands.Range[int, 0, 68703999],
    bonus: app_commands.Range[int, 0, 68703999],
) -> None:
    values = ShardState(text, voice, bonus)
    try:
        values.validate()
    except ValueError:
        await interaction.response.send_message(messages.SHARD_RANGE_ERROR, ephemeral=True)
        return
    bot = get_bot(interaction)
    await interaction.response.defer(ephemeral=True)
    data = await bot.db.leveling_state.set_shards(user.id, values)
    logger.info(
        "シャードを設定しました: command=/leveling shard set guild_id=%s actor_id=%s target_id=%s values=%s",
        interaction.guild_id,
        interaction.user.id,
        user.id,
        values,
    )
    notice = messages.SET_COMPLETED
    if interaction.guild is not None:
        member = interaction.guild.get_member(user.id)
        if member is not None:
            try:
                await sync_grade_prestige_role(bot, member, data)
            except discord.HTTPException:
                logger.exception("設定後の報酬ロール同期に失敗しました: target_id=%s", user.id)
                notice += messages.ROLE_SYNC_FAILED
    await interaction.followup.send(notice, ephemeral=True)


@app_commands.command(name="set", description=messages.POWER_SET_DESCRIPTION)
@app_commands.rename(
    user=messages.USER_LABEL, text=messages.TEXT_LABEL, voice=messages.VOICE_LABEL, action=messages.ACTION_LABEL
)
@app_commands.describe(
    user=messages.USER_DESCRIPTION,
    text=messages.AMOUNT_DESCRIPTION,
    voice=messages.AMOUNT_DESCRIPTION,
    action=messages.AMOUNT_DESCRIPTION,
)
@admin_only
async def set_powers(
    interaction: discord.Interaction,
    user: discord.User,
    text: app_commands.Range[int, 0, 4294967295],
    voice: app_commands.Range[int, 0, 4294967295],
    action: app_commands.Range[int, 0, 4294967295],
) -> None:
    values = PowerState(text, voice, action)
    try:
        values.validate()
    except ValueError:
        await interaction.response.send_message(messages.POWER_RANGE_ERROR, ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    await get_bot(interaction).db.leveling_state.set_powers(user.id, values)
    logger.info(
        "パワーを設定しました: command=/leveling power set guild_id=%s actor_id=%s target_id=%s values=%s",
        interaction.guild_id,
        interaction.user.id,
        user.id,
        values,
    )
    await interaction.followup.send(messages.SET_COMPLETED, ephemeral=True)


def register_set_commands() -> None:
    register_pending_command()
    if admin_shard_group.get_command("set") is None:
        admin_shard_group.add_command(set_shards)
    if admin_power_group.get_command("set") is None:
        admin_power_group.add_command(set_powers)
