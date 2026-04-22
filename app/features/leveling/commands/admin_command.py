from __future__ import annotations

import discord
from discord import app_commands

from app.common.command_groups import get_bot, register_group
from app.common.permissions import ADMINISTRATOR_PERMISSIONS, admin_only
from app.common.utils import humanize_number
from app.core.bot import AsteroidBot
from app.features.leveling.build_send_message import build_power_embed, build_star_grade_embed
from app.features.leveling.manage_reward_role import sync_grade_prestige_role

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


@xp_boost_group.command(name="add", description="経験値ブースターを追加します")
@admin_only
async def xp_boost_add(interaction: discord.Interaction, role: discord.Role, name: str, amount: int) -> None:
    bot = get_bot(interaction)
    await bot.db.xp_boosts.create_xp_boost(role.id, name, amount, None)
    await interaction.response.send_message("経験値ブースターを追加しました。")


@xp_boost_group.command(name="delete", description="経験値ブースターを削除します")
@admin_only
async def xp_boost_delete(interaction: discord.Interaction, role: discord.Role) -> None:
    bot = get_bot(interaction)
    await bot.db.xp_boosts.delete_xp_boost(role.id)
    await interaction.response.send_message("経験値ブースターを削除しました。")


@admin_shard_group.command(name="add", description="ユーザーにシャードを追加します")
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
        content=f"{user.mention}に`{humanize_number(amount)}`{shard_type_value}シャードを付与しました\n{grade_up_amount}回グレードアップしました、{prestige_up_amount}回プレステージしました",
        embed=build_star_grade_embed(user, star_grade),
    )
    await sync_grade_prestige_role(bot, user, star_grade)


@admin_shard_group.command(name="remove", description="ユーザーからシャードを減らします")
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
        content=f"{user.mention}から`{humanize_number(amount)}`{shard_type_value}シャードを減らしました",
        embed=build_star_grade_embed(user, star_grade),
    )
    await sync_grade_prestige_role(bot, user, star_grade)


@admin_power_group.command(name="add", description="ユーザーにパワーを追加します")
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
        async with bot.db.session() as session:
            action_power = await bot.db.monthly_action_powers.get_monthly_action_power_lock(
                session, user.id
            ) or await bot.db.monthly_action_powers.create_monthly_action_power_lock(session, user.id)
            await bot.db.monthly_action_powers.add_action_power_lock(session, action_power, amount)
            await session.commit()
        power = await bot.db.monthly_powers.get_monthly_power(user.id)
    else:
        power = await bot.db.monthly_powers.get_monthly_power(user.id)
        if power is None:
            power = await bot.db.monthly_powers.create_monthly_power(user.id)
        power = await (
            bot.db.monthly_powers.add_text_power(power, amount)
            if target_value == "text"
            else bot.db.monthly_powers.add_voice_power(power, amount)
        )
    await interaction.response.send_message(embed=build_power_embed(user, power))


@admin_power_group.command(name="remove", description="ユーザーからパワーを減らします")
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
        async with bot.db.session() as session:
            action_power = await bot.db.monthly_action_powers.get_monthly_action_power_lock(
                session, user.id
            ) or await bot.db.monthly_action_powers.create_monthly_action_power_lock(session, user.id)
            await bot.db.monthly_action_powers.remove_action_power_lock(session, action_power, amount)
            await session.commit()
        power = await bot.db.monthly_powers.get_monthly_power(user.id)
    else:
        power = await bot.db.monthly_powers.get_monthly_power(user.id)
        if power is None:
            power = await bot.db.monthly_powers.create_monthly_power(user.id)
        power = await (
            bot.db.monthly_powers.remove_text_power(power, amount)
            if target_value == "text"
            else bot.db.monthly_powers.remove_voice_power(power, amount)
        )
    await interaction.response.send_message(embed=build_power_embed(user, power))


@admin_power_group.command(name="reset_ranking", description="パワーランキングを更新してリセットします")
@admin_only
async def reset_power_ranking(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    await bot.db.monthly_powers.truncate_table()
    await bot.db.monthly_action_powers.truncate_table()
    await bot.db.voice_xp_limits.reset_voice_power()
    await interaction.response.send_message("月間パワーランキングをリセットしました。")


def register_leveling_admin_commands(bot: AsteroidBot) -> None:
    register_group(bot, leveling_admin_group)


async def setup(bot: AsteroidBot) -> None:
    register_leveling_admin_commands(bot)
