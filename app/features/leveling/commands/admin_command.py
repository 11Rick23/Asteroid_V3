from __future__ import annotations

from logging import getLogger

import discord
from discord import app_commands

from app.common.command_groups import get_bot, register_group
from app.common.permissions import ADMINISTRATOR_PERMISSIONS, admin_only
from app.common.utils import humanize_number
from app.core.bot import AsteroidBot
from app.features.leveling import messages
from app.features.leveling.action_power import build_accumulated_action_power_message
from app.features.leveling.build_send_message import build_power_view, build_star_grade_view
from app.features.leveling.manage_reward_role import sync_grade_prestige_role
from app.features.leveling.monthly import run_monthly_ranking

logger = getLogger(__name__)

leveling_admin_group = app_commands.Group(
    name="leveling",
    description=messages.ADMIN_GROUP_DESCRIPTION,
    guild_only=True,
    default_permissions=ADMINISTRATOR_PERMISSIONS,
)
xp_boost_group = app_commands.Group(
    name="booster", description=messages.BOOSTER_GROUP_DESCRIPTION, parent=leveling_admin_group
)
admin_shard_group = app_commands.Group(
    name="shard", description=messages.ADMIN_SHARD_GROUP_DESCRIPTION, parent=leveling_admin_group
)
admin_power_group = app_commands.Group(
    name="power", description=messages.ADMIN_POWER_GROUP_DESCRIPTION, parent=leveling_admin_group
)
SHARD_TYPE_CHOICES = [
    app_commands.Choice(name=messages.TEXT_LABEL, value=messages.TEXT_LABEL),
    app_commands.Choice(name=messages.VOICE_LABEL, value=messages.VOICE_LABEL),
    app_commands.Choice(name=messages.BONUS_LABEL, value=messages.BONUS_LABEL),
]
POWER_TYPE_CHOICES = [
    app_commands.Choice(name=messages.TEXT_LABEL, value="text"),
    app_commands.Choice(name=messages.VOICE_LABEL, value="voice"),
    app_commands.Choice(name=messages.ACTION_LABEL, value="action"),
]


@leveling_admin_group.command(name="action_power_total", description=messages.ACTION_POWER_TOTAL_DESCRIPTION)
@admin_only
async def action_power_total(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    total_action_power = await bot.db.monthly_action_powers.sum_action_power()
    logger.info(
        "合計アクションパワーを確認しました: command=/leveling action_power_total "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"actor_id={interaction.user.id} total_action_power={total_action_power}"
    )
    await interaction.response.send_message(
        build_accumulated_action_power_message(total_action_power),
        ephemeral=True,
    )


@xp_boost_group.command(name="add", description=messages.BOOSTER_ADD_DESCRIPTION)
@app_commands.rename(role=messages.ROLE_LABEL, name=messages.NAME_LABEL, amount=messages.MULTIPLIER_LABEL)
@admin_only
async def xp_boost_add(interaction: discord.Interaction, role: discord.Role, name: str, amount: int) -> None:
    bot = get_bot(interaction)
    await bot.db.xp_boosts.create_xp_boost(role.id, name, amount, None)
    logger.info(
        "XPブースターを追加しました: command=/leveling booster add "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"actor_id={interaction.user.id} role_id={role.id} name={name} amount={amount}"
    )
    await interaction.response.send_message(messages.BOOSTER_ADDED)


@xp_boost_group.command(name="delete", description=messages.BOOSTER_DELETE_DESCRIPTION)
@app_commands.rename(role=messages.ROLE_LABEL)
@admin_only
async def xp_boost_delete(interaction: discord.Interaction, role: discord.Role) -> None:
    bot = get_bot(interaction)
    await bot.db.xp_boosts.delete_xp_boost(role.id)
    logger.info(
        "XPブースターを削除しました: command=/leveling booster delete "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"actor_id={interaction.user.id} role_id={role.id}"
    )
    await interaction.response.send_message(messages.BOOSTER_DELETED)


@admin_shard_group.command(name="add", description=messages.SHARD_ADD_DESCRIPTION)
@app_commands.rename(user=messages.USER_LABEL, shard_type=messages.SHARD_TYPE_LABEL, amount=messages.AMOUNT_LABEL)
@app_commands.choices(shard_type=SHARD_TYPE_CHOICES)
@admin_only
async def add_shard(
    interaction: discord.Interaction,
    user: discord.Member,
    shard_type: app_commands.Choice[str],
    amount: int,
) -> None:
    bot = get_bot(interaction)
    shard_type_value = shard_type.value
    update = await bot.db.leveling.add_shard(user.id, shard_type_value, amount)
    await interaction.response.send_message(
        view=build_star_grade_view(
            user,
            update.star_grade,
            notice=messages.shard_added(
                user_mention=user.mention,
                amount=humanize_number(amount),
                shard_type=shard_type_value,
                grade_up_amount=update.grade_up_amount,
                prestige_amount=update.prestige_amount,
            ),
        )
    )
    await sync_grade_prestige_role(bot, user, update.star_grade)
    logger.info(
        "シャードを加算しました: command=/leveling shard add "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"target_id={user.id} shard_type={shard_type_value} amount={amount} "
        f"grade={update.star_grade.grade} prestige={update.star_grade.prestige}"
    )


@admin_shard_group.command(name="remove", description=messages.SHARD_REMOVE_DESCRIPTION)
@app_commands.rename(user=messages.USER_LABEL, shard_type=messages.SHARD_TYPE_LABEL, amount=messages.AMOUNT_LABEL)
@app_commands.choices(shard_type=SHARD_TYPE_CHOICES)
@admin_only
async def remove_shard(
    interaction: discord.Interaction,
    user: discord.Member,
    shard_type: app_commands.Choice[str],
    amount: int,
) -> None:
    bot = get_bot(interaction)
    shard_type_value = shard_type.value
    update = await bot.db.leveling.remove_shard(user.id, shard_type_value, amount)
    await interaction.response.send_message(
        view=build_star_grade_view(
            user,
            update.star_grade,
            notice=messages.shard_removed(
                user_mention=user.mention,
                amount=humanize_number(amount),
                shard_type=shard_type_value,
            ),
        )
    )
    await sync_grade_prestige_role(bot, user, update.star_grade)
    logger.info(
        "シャードを減算しました: command=/leveling shard remove "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"target_id={user.id} shard_type={shard_type_value} amount={amount} "
        f"grade={update.star_grade.grade} prestige={update.star_grade.prestige}"
    )


@admin_power_group.command(name="add", description=messages.POWER_ADD_DESCRIPTION)
@app_commands.rename(user=messages.USER_LABEL, target=messages.POWER_TYPE_LABEL, amount=messages.AMOUNT_LABEL)
@app_commands.choices(target=POWER_TYPE_CHOICES)
@admin_only
async def add_power(
    interaction: discord.Interaction,
    user: discord.Member,
    target: app_commands.Choice[str],
    amount: int,
) -> None:
    bot = get_bot(interaction)
    target_value = target.value
    power = await bot.db.leveling.add_power(user.id, target_value, amount)
    logger.info(
        "パワーを加算しました: command=/leveling power add "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"target_id={user.id} power_type={target_value} amount={amount}"
    )
    await interaction.response.send_message(view=build_power_view(user, power))


@admin_power_group.command(name="remove", description=messages.POWER_REMOVE_DESCRIPTION)
@app_commands.rename(user=messages.USER_LABEL, target=messages.POWER_TYPE_LABEL, amount=messages.AMOUNT_LABEL)
@app_commands.choices(target=POWER_TYPE_CHOICES)
@admin_only
async def remove_power(
    interaction: discord.Interaction,
    user: discord.Member,
    target: app_commands.Choice[str],
    amount: int,
) -> None:
    bot = get_bot(interaction)
    target_value = target.value
    power = await bot.db.leveling.remove_power(user.id, target_value, amount)
    logger.info(
        "パワーを減算しました: command=/leveling power remove "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"target_id={user.id} power_type={target_value} amount={amount}"
    )
    await interaction.response.send_message(view=build_power_view(user, power))


@admin_power_group.command(name="aggregate", description=messages.AGGREGATE_DESCRIPTION)
@app_commands.rename(delete_data=messages.DELETE_DATA_LABEL)
@app_commands.describe(delete_data=messages.AGGREGATE_DELETE_DESCRIPTION)
@admin_only
async def aggregate_power_ranking(interaction: discord.Interaction, delete_data: bool = False) -> None:
    bot = get_bot(interaction)
    await interaction.response.defer(ephemeral=True)
    ranked_count = await run_monthly_ranking(
        bot,
        force=True,
        delete_data=delete_data,
    )
    if ranked_count is None:
        logger.warning(
            "月間パワーランキングの手動集計に失敗しました: command=/leveling power aggregate "
            f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
            f"actor_id={interaction.user.id} data_deleted={delete_data}"
        )
        await interaction.followup.send(messages.AGGREGATE_FAILED, ephemeral=True)
        return

    logger.info(
        "月間パワーランキングを手動集計しました: command=/leveling power aggregate "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"actor_id={interaction.user.id} ranked_count={ranked_count} data_deleted={delete_data}"
    )
    await interaction.followup.send(
        messages.aggregate_result(ranked_count=ranked_count, delete_data=delete_data),
        ephemeral=True,
    )


def register_leveling_admin_commands(bot: AsteroidBot) -> None:
    register_group(bot, leveling_admin_group)


async def setup(bot: AsteroidBot) -> None:
    register_leveling_admin_commands(bot)
