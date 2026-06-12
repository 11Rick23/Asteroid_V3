from __future__ import annotations

from logging import getLogger

import discord
from discord import app_commands

from app.common.command_groups import get_bot, register_group
from app.common.constants import AsteroidColor, AsteroidEmoji
from app.common.layout_pages import LayoutPaginator
from app.common.pages import PaginatorButton
from app.core.bot import AsteroidBot
from app.features.leveling.build_send_message import (
    build_shard_ranking_pages,
    build_text_container,
    build_text_view,
)

logger = getLogger(__name__)

shard_group = app_commands.Group(name="shard", description="恒常ランキング系コマンド")
reward_group = app_commands.Group(
    name="reward", description="グレード・プレステージ報酬関連のコマンド", parent=shard_group
)
RANKING_PAGE_SIZE = 5


@shard_group.command(name="top", description="現在の恒常ランキングを表示します")
async def top(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    star_grades = await bot.db.star_grades.get_star_grade_ranking()
    logger.debug(
        "シャードランキングを表示しました: command=/shard top "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"user_id={interaction.user.id} result_count={len(star_grades)}"
    )
    pages = build_shard_ranking_pages(
        bot,
        star_grades,
        title="シャードランキング",
        description=(
            "現在のシャードランキングを表示します\n\n"
            f"{AsteroidEmoji.PRESTIGE}: プレステージ\n"
            f"{AsteroidEmoji.GRADE}: グレード\n"
            f"{AsteroidEmoji.SHARD}: シャード\n"
            f"{AsteroidEmoji.TRANSPARENT}"
        ),
        page_size=RANKING_PAGE_SIZE,
    )
    paginator = LayoutPaginator(pages=pages, use_default_buttons=False, loop_pages=False, show_disabled=True)
    paginator.add_button(PaginatorButton("prev", label="<", style=discord.ButtonStyle.green))
    paginator.add_button(PaginatorButton("page_indicator", style=discord.ButtonStyle.gray))
    paginator.add_button(PaginatorButton("next", label=">", style=discord.ButtonStyle.green))
    await paginator.respond(interaction)


@shard_group.command(name="xp_boost", description="現在開催中のXPブーストを表示します")
async def xp_boost(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    xp_boosts = await bot.db.xp_boosts.get_xp_boosts()
    if len(xp_boosts) == 0:
        logger.debug(
            "XPブースト一覧を表示しました: command=/shard xp_boost "
            f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
            f"user_id={interaction.user.id} result_count=0"
        )
        await interaction.response.send_message("現在開催中のXPブーストはありません")
        return
    logger.debug(
        "XPブースト一覧を表示しました: command=/shard xp_boost "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"user_id={interaction.user.id} result_count={len(xp_boosts)}"
    )
    pages: list[discord.ui.Container] = []
    for start in range(0, len(xp_boosts), 10):
        entries = []
        for boost in xp_boosts[start : start + 10]:
            role = interaction.guild.get_role(boost.role_id) if interaction.guild is not None else None
            entries.append(
                f"### {boost.name}\n"
                f"対象ロール: {role.mention if role else 'ロールが見つかりません'}\n"
                f"ブースト量: {boost.boost_amount}%\n"
                "ブースト終了時間: "
                f"{discord.utils.format_dt(boost.boost_end_time, 'f') if boost.boost_end_time else '無期限'}"
            )
        pages.append(
            build_text_container(
                "# 開催中のXPブースト一覧\n"
                "現在開催中のXPブーストです\n"
                "XPブーストはシャードのみに適用されます、"
                "パワーには全く影響がありませんのでご注意ください\n\n" + "\n\n".join(entries)
            )
        )
    paginator = LayoutPaginator(pages=pages, use_default_buttons=False, loop_pages=False, show_disabled=False)
    paginator.add_button(PaginatorButton("prev", label="<", style=discord.ButtonStyle.green))
    paginator.add_button(PaginatorButton("page_indicator", style=discord.ButtonStyle.gray, disabled=True))
    paginator.add_button(PaginatorButton("next", label=">", style=discord.ButtonStyle.green))
    await paginator.respond(interaction)


@reward_group.command(name="grade", description="グレードに応じたロール報酬を表示します")
async def reward_grade(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    grade_roles = bot.config.leveling.grade_roles_id_list
    logger.debug(
        "グレード報酬一覧を表示しました: command=/shard reward grade "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"user_id={interaction.user.id} result_count={len(grade_roles)}"
    )
    entries = []
    for grade_role in grade_roles:
        role = interaction.guild.get_role(grade_role.role_id) if interaction.guild is not None else None
        entries.append(f"### Grade. {grade_role.grade}\n{role.mention if role else 'ロールが見つかりません'}")
    await interaction.response.send_message(
        view=build_text_view(
            "# グレードロール報酬\n"
            "グレードに応じたロール報酬を表示します\n\n"
            + ("\n\n".join(entries) if entries else "報酬ロールは設定されていません。"),
            accent_color=AsteroidColor.INFO,
        )
    )


@reward_group.command(name="prestige", description="プレステージに応じたロール報酬を表示します")
async def reward_prestige(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    prestige_roles = bot.config.leveling.prestige_roles_id_list
    logger.debug(
        "プレステージ報酬一覧を表示しました: command=/shard reward prestige "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"user_id={interaction.user.id} result_count={len(prestige_roles)}"
    )
    entries = []
    for prestige_role in prestige_roles:
        role = interaction.guild.get_role(prestige_role.role_id) if interaction.guild is not None else None
        entries.append(f"### Prestige. {prestige_role.prestige}\n{role.mention if role else 'ロールが見つかりません'}")
    await interaction.response.send_message(
        view=build_text_view(
            "# プレステージロール報酬\n"
            "プレステージに応じたロール報酬を表示します\n\n"
            + ("\n\n".join(entries) if entries else "報酬ロールは設定されていません。"),
            accent_color=AsteroidColor.INFO,
        )
    )


def register_shard_commands(bot: AsteroidBot) -> None:
    register_group(bot, shard_group)


async def setup(bot: AsteroidBot) -> None:
    register_shard_commands(bot)
