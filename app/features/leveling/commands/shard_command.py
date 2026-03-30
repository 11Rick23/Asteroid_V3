from __future__ import annotations

import discord
from discord import app_commands

from app.common.command_groups import get_bot, register_group
from app.common.constants import AsteroidColor, AsteroidEmoji
from app.common.pages import Paginator, PaginatorButton
from app.core.bot import AsteroidBot
from app.features.leveling.build_send_message import build_shard_ranking_embed

shard_group = app_commands.Group(name="shard", description="恒常ランキング系コマンド")
reward_group = app_commands.Group(
    name="reward", description="グレード・プレステージ報酬関連のコマンド", parent=shard_group
)


@shard_group.command(name="top", description="現在の恒常ランキングを表示します")
async def top(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    star_grades = await bot.db.star_grades.get_star_grade_ranking()
    base_embed = discord.Embed(
        title="シャードランキング",
        description="現在のシャードランキングを表示します\n\n"
        f"{AsteroidEmoji.PRESTIGE}: プレステージ\n"
        f"{AsteroidEmoji.GRADE}: グレード\n"
        f"{AsteroidEmoji.SHARD}: シャード\n"
        f"{AsteroidEmoji.TRANSPARENT}",
        color=AsteroidColor.INFO,
    )
    embeds = build_shard_ranking_embed(bot, star_grades, base_embed)
    paginator = Paginator(pages=embeds, use_default_buttons=False, loop_pages=False, show_disabled=False)
    paginator.add_button(PaginatorButton("prev", label="<", style=discord.ButtonStyle.green))
    paginator.add_button(PaginatorButton("page_indicator", style=discord.ButtonStyle.gray, disabled=True))
    paginator.add_button(PaginatorButton("next", label=">", style=discord.ButtonStyle.green))
    await paginator.respond(interaction)


@shard_group.command(name="xp_boost", description="現在開催中のXPブーストを表示します")
async def xp_boost(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    xp_boosts = await bot.db.xp_boosts.get_xp_boosts()
    if len(xp_boosts) == 0:
        await interaction.response.send_message("現在開催中のXPブーストはありません")
        return
    base_embed = discord.Embed(
        title="開催中のXPブースト一覧",
        description="現在開催中のXPブーストです\nXPブーストはシャードのみに適用されます、パワーには全く影響がありませんのでご注意ください",
        color=AsteroidColor.INFO,
    )
    embeds: list[discord.Embed] = []
    for i, boost in enumerate(xp_boosts):
        page_num = i // 10
        if len(embeds) <= page_num:
            embeds.append(base_embed.copy())
        role = interaction.guild.get_role(boost.role_id)
        embeds[page_num].add_field(
            name=boost.name,
            value=f"対象ロール: {role.mention if role else 'ロールが見つかりません'}\n"
            f"ブースト量: {boost.boost_amount}%\n"
            "ブースト終了時間: "
            f"{discord.utils.format_dt(boost.boost_end_time, 'f') if boost.boost_end_time else '無期限'}",
            inline=False,
        )
    paginator = Paginator(pages=embeds, use_default_buttons=False, loop_pages=False, show_disabled=False)
    paginator.add_button(PaginatorButton("prev", label="<", style=discord.ButtonStyle.green))
    paginator.add_button(PaginatorButton("page_indicator", style=discord.ButtonStyle.gray, disabled=True))
    paginator.add_button(PaginatorButton("next", label=">", style=discord.ButtonStyle.green))
    await paginator.respond(interaction)


@reward_group.command(name="grade", description="グレードに応じたロール報酬を表示します")
async def reward_grade(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    grade_roles = bot.config.leveling.grade_roles_id_list
    embed = discord.Embed(
        title="グレードロール報酬", description="グレードに応じたロール報酬を表示します", color=AsteroidColor.INFO
    )
    for grade_role in grade_roles:
        role = interaction.guild.get_role(grade_role.role_id)
        embed.add_field(
            name=f"Grade. {grade_role.grade}",
            value=role.mention if role else "ロールが見つかりません",
            inline=True,
        )
    await interaction.response.send_message(embed=embed)


@reward_group.command(name="prestige", description="プレステージに応じたロール報酬を表示します")
async def reward_prestige(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    prestige_roles = bot.config.leveling.prestige_roles_id_list
    embed = discord.Embed(
        title="プレステージロール報酬",
        description="プレステージに応じたロール報酬を表示します",
        color=AsteroidColor.INFO,
    )
    for prestige_role in prestige_roles:
        role = interaction.guild.get_role(prestige_role.role_id)
        embed.add_field(
            name=f"Prestige. {prestige_role.prestige}",
            value=role.mention if role else "ロールが見つかりません",
            inline=True,
        )
    await interaction.response.send_message(embed=embed)


def register_shard_commands(bot: AsteroidBot) -> None:
    register_group(bot, shard_group)


async def setup(bot: AsteroidBot) -> None:
    register_shard_commands(bot)
