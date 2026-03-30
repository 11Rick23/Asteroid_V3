from __future__ import annotations

import discord

from app.common.constants import AsteroidColor, AsteroidEmoji
from app.common.utils import humanize_number
from app.core.bot import AsteroidBot
from app.database.repositories.monthly_powers import MonthlyPowerData, MonthlyPowerRankingData
from app.database.repositories.star_grades import StarGradeData, StarGradeRankingData
from app.features.leveling.domain.math_calculation import next_grade_progress, total_shard_amount


async def send_grade_up_message(
    channel: discord.abc.Messageable, author: discord.User | discord.Member, grade: int, grade_up_amount: int
) -> None:
    if isinstance(channel, discord.StageChannel):
        return
    await channel.send(
        embeds=[
            discord.Embed(
                title="レベルアップ！",
                description=(
                    f"**{author.mention}さんがGrade. {grade - grade_up_amount}からGrade. {grade}へグレードアップ！**"
                ),
                color=discord.Color.random(),
            )
        ]
    )


async def send_prestige_up_message(
    channel: discord.abc.Messageable, author: discord.User | discord.Member, prestige: int, prestige_amount: int
) -> None:
    if isinstance(channel, discord.StageChannel):
        return
    await channel.send(
        embeds=[
            discord.Embed(
                title="プレステージ！",
                description=(
                    f"**{author.mention}さんがPrestige. {prestige - prestige_amount}から"
                    f"Prestige. {prestige}へプレステージ！**"
                ),
                color=discord.Color.random(),
            )
        ]
    )


async def send_prestige_announce(bot: AsteroidBot, member: discord.Member, prestige: int) -> None:
    prestige_role_ids = bot.config.leveling.prestige_roles_id_list
    prestige_announce_channel_id = bot.config.leveling.prestige_announce_channel_id
    prestige_role = None
    if prestige_role_ids:
        prestige_roles = sorted(
            filter(lambda role: role.prestige <= prestige, prestige_role_ids),
            key=lambda role: role.prestige,
            reverse=True,
        )
        if prestige_roles:
            prestige_role = member.guild.get_role(prestige_roles[0].role_id)
    if prestige_announce_channel_id == 0:
        return
    channel = bot.get_channel(prestige_announce_channel_id)
    if channel is None:
        return
    await channel.send(
        f"> {member.mention}さんが"
        f"{prestige_role.mention if prestige_role else f'プレステージ{prestige}'}を達成しました！\n"
        "> おめでとうございます！"
    )


def build_star_grade_embed(user: discord.abc.User, star_grade: StarGradeData | StarGradeRankingData) -> discord.Embed:
    grade_progress, grade_progress_bar = next_grade_progress(star_grade.grade, star_grade.shard)
    description_prefix = (
        f"**現在の順位: {star_grade.ranking}位\n\n" if isinstance(star_grade, StarGradeRankingData) else "**"
    )
    embed = discord.Embed(
        description=description_prefix
        + (
            f"{AsteroidEmoji.GRADE}Grade. {star_grade.grade + 1}までの進捗ケージ\n"
            f"{grade_progress_bar} {grade_progress}%**"
        ),
        color=AsteroidColor.INFO,
    )
    embed.set_author(name=f"{user.display_name}のシャード", icon_url=user.display_avatar.url)
    embed.add_field(
        name="プレステージ数",
        value=f"{AsteroidEmoji.PRESTIGE} {format_prestige_num(star_grade.prestige)}",
        inline=True,
    )
    embed.add_field(name="グレード数", value=f"{AsteroidEmoji.GRADE} {star_grade.grade}", inline=True)
    embed.add_field(name="シャード数", value=f"{AsteroidEmoji.SHARD} {humanize_number(star_grade.shard)}", inline=True)
    embed.add_field(
        name="累計テキストシャード数",
        value=f"{AsteroidEmoji.TEXT_SHARD} {humanize_number(star_grade.text_shard)}",
        inline=True,
    )
    embed.add_field(
        name="累計ボイスシャード数",
        value=f"{AsteroidEmoji.VOICE_SHARD} {humanize_number(star_grade.voice_shard)}",
        inline=True,
    )
    embed.add_field(
        name="累計ボーナスシャード",
        value=f"{AsteroidEmoji.BONUS_SHARD} {humanize_number(star_grade.bonus_shard)}",
        inline=True,
    )
    return embed


def build_shard_ranking_embed(
    bot: AsteroidBot, star_grades: list[StarGradeRankingData], base_embed: discord.Embed
) -> list[discord.Embed]:
    embeds: list[discord.Embed] = []
    for i, star_grade in enumerate(star_grades):
        page_num = i // 10
        if len(embeds) <= page_num:
            embeds.append(base_embed.copy())
        embed = embeds[page_num]
        user = bot.get_user(star_grade.user_id)
        display_name = user.display_name if user else f"不明なメンバー [{star_grade.user_id}]"
        total_shards = total_shard_amount(star_grade.prestige, star_grade.grade, star_grade.shard)
        embed.add_field(
            name=f"{star_grade.ranking}位: {display_name}",
            value=f"計: {humanize_number(total_shards)}\n"
            f"{AsteroidEmoji.PRESTIGE} {format_prestige_num(star_grade.prestige)}{AsteroidEmoji.TRANSPARENT}"
            f"{AsteroidEmoji.GRADE} {star_grade.grade}{AsteroidEmoji.TRANSPARENT}"
            f"{AsteroidEmoji.SHARD} {humanize_number(star_grade.shard)}",
            inline=False,
        )
    return embeds


def build_power_embed(
    user: discord.abc.User, monthly_power: MonthlyPowerData | MonthlyPowerRankingData
) -> discord.Embed:
    embed = discord.Embed(
        description=f"**現在の順位: {monthly_power.ranking}位**"
        if isinstance(monthly_power, MonthlyPowerRankingData)
        else None,
        color=AsteroidColor.INFO,
    )
    embed.set_author(name=f"{user.display_name}のパワー", icon_url=user.display_avatar.url)
    embed.add_field(
        name="テキストパワー数",
        value=f"{AsteroidEmoji.TEXT_POWER} {humanize_number(monthly_power.text_power)}",
        inline=True,
    )
    embed.add_field(
        name="ボイスパワー数",
        value=f"{AsteroidEmoji.VOICE_POWER} {humanize_number(monthly_power.voice_power)}",
        inline=True,
    )
    return embed


def build_power_ranking_embed(
    bot: AsteroidBot, monthly_powers: list[MonthlyPowerRankingData], base_embed: discord.Embed
) -> list[discord.Embed]:
    embeds: list[discord.Embed] = []
    for i, monthly_power in enumerate(monthly_powers):
        page_num = i // 10
        if len(embeds) <= page_num:
            embeds.append(base_embed.copy())
        embed = embeds[page_num]
        user = bot.get_user(monthly_power.user_id)
        display_name = user.display_name if user else f"不明なメンバー [{monthly_power.user_id}]"
        embed.add_field(
            name=f"{monthly_power.ranking}位: {display_name}",
            value=f"{AsteroidEmoji.TEXT_POWER} {humanize_number(monthly_power.text_power)}"
            f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.VOICE_POWER} {humanize_number(monthly_power.voice_power)}"
            f"{AsteroidEmoji.TRANSPARENT}計: {humanize_number(monthly_power.text_power + monthly_power.voice_power)}",
            inline=False,
        )
    if monthly_powers:
        top_power_user = bot.get_user(monthly_powers[0].user_id)
        if top_power_user is not None:
            embeds[0].set_thumbnail(url=top_power_user.display_avatar.url)
    return embeds


def build_rank_embed(
    user: discord.abc.User, monthly_power: MonthlyPowerRankingData, star_grade: StarGradeRankingData
) -> discord.Embed:
    grade_progress, grade_progress_bar = next_grade_progress(star_grade.grade, star_grade.shard)
    total_shards = total_shard_amount(star_grade.prestige, star_grade.grade, star_grade.shard)
    total_power = monthly_power.text_power + monthly_power.voice_power
    embed = discord.Embed(
        description=f"次のグレードまで…\n## {grade_progress_bar} {grade_progress}%\n", color=AsteroidColor.INFO
    )
    embed.set_author(name=f"{user.display_name}のランクカード", icon_url=user.display_avatar.url)
    embed.add_field(
        name=f"{humanize_number(total_shards)}シャード - 現在{star_grade.ranking}位",
        value=f"{AsteroidEmoji.PRESTIGE} {format_prestige_num(star_grade.prestige)}{AsteroidEmoji.TRANSPARENT}"
        f"{AsteroidEmoji.GRADE} {star_grade.grade}{AsteroidEmoji.TRANSPARENT}"
        f"{AsteroidEmoji.SHARD} {humanize_number(star_grade.shard)}\n"
        f"{AsteroidEmoji.TEXT_SHARD} {humanize_number(star_grade.text_shard)}{AsteroidEmoji.TRANSPARENT}"
        f"{AsteroidEmoji.VOICE_SHARD} {humanize_number(star_grade.voice_shard)}{AsteroidEmoji.TRANSPARENT}"
        f"{AsteroidEmoji.BONUS_SHARD} {humanize_number(star_grade.bonus_shard)}\n"
        f"{AsteroidEmoji.TRANSPARENT}",
        inline=False,
    )
    embed.add_field(
        name=f"{humanize_number(total_power)}パワー - 現在{monthly_power.ranking}位",
        value=f"{AsteroidEmoji.TEXT_POWER} {humanize_number(monthly_power.text_power)}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.VOICE_POWER} {humanize_number(monthly_power.voice_power)}",
        inline=False,
    )
    return embed


def format_prestige_num(prestige: int) -> str:
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    roman_numeral = ""
    i = 0
    if prestige == 0:
        return "-"
    while prestige > 0:
        for _ in range(prestige // val[i]):
            roman_numeral += syms[i]
            prestige -= val[i]
        i += 1
    return roman_numeral if i > 0 else "0"
