from __future__ import annotations

from logging import getLogger

import discord
from discord import app_commands

from app.common.command_groups import get_bot, register_group
from app.common.permissions import ADMINISTRATOR_PERMISSIONS, admin_only
from app.common.utils import humanize_number
from app.core.bot import AsteroidBot
from app.features.leveling.action_power import build_accumulated_action_power_message
from app.features.leveling.build_send_message import build_power_view, build_star_grade_view
from app.features.leveling.manage_reward_role import sync_grade_prestige_role

logger = getLogger(__name__)

leveling_admin_group = app_commands.Group(
    name="leveling",
    description="管理者用レベリングシステム関連コマンド",
    guild_only=True,
    default_permissions=ADMINISTRATOR_PERMISSIONS,
)
xp_boost_group = app_commands.Group(name="booster", description="ブースター設定", parent=leveling_admin_group)
admin_shard_group = app_commands.Group(name="shard", description="シャード管理", parent=leveling_admin_group)
admin_power_group = app_commands.Group(name="power", description="パワー管理", parent=leveling_admin_group)
SHARD_TYPE_CHOICES = [
    app_commands.Choice(name="テキスト", value="テキスト"),
    app_commands.Choice(name="ボイス", value="ボイス"),
    app_commands.Choice(name="ボーナス", value="ボーナス"),
]
POWER_TYPE_CHOICES = [
    app_commands.Choice(name="テキスト", value="text"),
    app_commands.Choice(name="ボイス", value="voice"),
    app_commands.Choice(name="アクション", value="action"),
]


@leveling_admin_group.command(name="action_power_total", description="現在の合計アクションパワーを確認します")
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


@xp_boost_group.command(name="add", description="経験値ブースターを追加します")
@app_commands.rename(role="ロール", name="名前", amount="倍率")
@admin_only
async def xp_boost_add(interaction: discord.Interaction, role: discord.Role, name: str, amount: int) -> None:
    bot = get_bot(interaction)
    await bot.db.xp_boosts.create_xp_boost(role.id, name, amount, None)
    logger.info(
        "XPブースターを追加しました: command=/leveling booster add "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"actor_id={interaction.user.id} role_id={role.id} name={name} amount={amount}"
    )
    await interaction.response.send_message("経験値ブースターを追加しました。")


@xp_boost_group.command(name="delete", description="経験値ブースターを削除します")
@app_commands.rename(role="ロール")
@admin_only
async def xp_boost_delete(interaction: discord.Interaction, role: discord.Role) -> None:
    bot = get_bot(interaction)
    await bot.db.xp_boosts.delete_xp_boost(role.id)
    logger.info(
        "XPブースターを削除しました: command=/leveling booster delete "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"actor_id={interaction.user.id} role_id={role.id}"
    )
    await interaction.response.send_message("経験値ブースターを削除しました。")


@admin_shard_group.command(name="add", description="ユーザーにシャードを追加します")
@app_commands.rename(user="ユーザー", shard_type="シャード種類", amount="数量")
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
    star_grade = await bot.db.star_grades.get_star_grade(user.id) or await bot.db.star_grades.create_star_grade(
        user.id
    )
    if shard_type_value == "テキスト":
        star_grade, grade_up_amount, prestige_up_amount = await bot.db.star_grades.add_text_shard(star_grade, amount)
    elif shard_type_value == "ボイス":
        star_grade, grade_up_amount, prestige_up_amount = await bot.db.star_grades.add_voice_shard(star_grade, amount)
    else:
        star_grade, grade_up_amount, prestige_up_amount = await bot.db.star_grades.add_bonus_shard(star_grade, amount)
    await interaction.response.send_message(
        view=build_star_grade_view(
            user,
            star_grade,
            notice=(
                f"{user.mention}に`{humanize_number(amount)}`{shard_type_value}シャードを付与しました\n"
                f"{grade_up_amount}回グレードアップしました、"
                f"{prestige_up_amount}回プレステージしました"
            ),
        )
    )
    await sync_grade_prestige_role(bot, user, star_grade)
    logger.info(
        "シャードを加算しました: command=/leveling shard add "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"target_id={user.id} shard_type={shard_type_value} amount={amount} "
        f"grade={star_grade.grade} prestige={star_grade.prestige}"
    )


@admin_shard_group.command(name="remove", description="ユーザーからシャードを減らします")
@app_commands.rename(user="ユーザー", shard_type="シャード種類", amount="数量")
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
    star_grade = await bot.db.star_grades.get_star_grade(user.id) or await bot.db.star_grades.create_star_grade(
        user.id
    )
    if shard_type_value == "テキスト":
        star_grade, _, _ = await bot.db.star_grades.remove_text_shard(star_grade, amount)
    elif shard_type_value == "ボイス":
        star_grade, _, _ = await bot.db.star_grades.remove_voice_shard(star_grade, amount)
    else:
        star_grade, _, _ = await bot.db.star_grades.remove_bonus_shard(star_grade, amount)
    await interaction.response.send_message(
        view=build_star_grade_view(
            user,
            star_grade,
            notice=f"{user.mention}から`{humanize_number(amount)}`{shard_type_value}シャードを減らしました",
        )
    )
    await sync_grade_prestige_role(bot, user, star_grade)
    logger.info(
        "シャードを減算しました: command=/leveling shard remove "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"target_id={user.id} shard_type={shard_type_value} amount={amount} "
        f"grade={star_grade.grade} prestige={star_grade.prestige}"
    )


@admin_power_group.command(name="add", description="ユーザーにパワーを追加します")
@app_commands.rename(user="ユーザー", target="パワー種類", amount="数量")
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
    if target_value == "action":
        await bot.db.leveling.add_action_power(user.id, amount)
        power = await bot.db.monthly_powers.get_monthly_power(user.id)
        if power is None:
            power = await bot.db.monthly_powers.create_monthly_power(user.id)
    else:
        power = await (
            bot.db.leveling.add_text_power(user.id, amount)
            if target_value == "text"
            else bot.db.leveling.add_voice_power(user.id, amount)
        )
    logger.info(
        "パワーを加算しました: command=/leveling power add "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"target_id={user.id} power_type={target_value} amount={amount}"
    )
    await interaction.response.send_message(view=build_power_view(user, power))


@admin_power_group.command(name="remove", description="ユーザーからパワーを減らします")
@app_commands.rename(user="ユーザー", target="パワー種類", amount="数量")
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
    if target_value == "action":
        await bot.db.leveling.remove_action_power(user.id, amount)
        power = await bot.db.monthly_powers.get_monthly_power(user.id)
        if power is None:
            power = await bot.db.monthly_powers.create_monthly_power(user.id)
    else:
        power = await bot.db.monthly_powers.get_monthly_power(user.id)
        if power is None:
            power = await bot.db.monthly_powers.create_monthly_power(user.id)
        power = await (
            bot.db.monthly_powers.remove_text_power(power, amount)
            if target_value == "text"
            else bot.db.monthly_powers.remove_voice_power(power, amount)
        )
    logger.info(
        "パワーを減算しました: command=/leveling power remove "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id} "
        f"target_id={user.id} power_type={target_value} amount={amount}"
    )
    await interaction.response.send_message(view=build_power_view(user, power))


@admin_power_group.command(name="reset_ranking", description="パワーランキングを更新してリセットします")
@admin_only
async def reset_power_ranking(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    await bot.db.monthly_powers.truncate_table()
    await bot.db.monthly_action_powers.truncate_table()
    await bot.db.voice_xp_limits.reset_voice_power()
    logger.info(
        "月間パワーランキングをリセットしました: command=/leveling power reset_ranking "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} actor_id={interaction.user.id}"
    )
    await interaction.response.send_message("月間パワーランキングをリセットしました。")


def register_leveling_admin_commands(bot: AsteroidBot) -> None:
    register_group(bot, leveling_admin_group)


async def setup(bot: AsteroidBot) -> None:
    register_leveling_admin_commands(bot)
