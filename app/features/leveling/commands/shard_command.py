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
from app.features.leveling.messages import common as common_messages
from app.features.leveling.messages import ranking as ranking_messages
from app.features.leveling.messages import rewards as reward_messages

logger = getLogger(__name__)

shard_group = app_commands.Group(name="shard", description=ranking_messages.SHARD_GROUP_DESCRIPTION)
reward_group = app_commands.Group(
    name="reward",
    description=reward_messages.REWARD_GROUP_DESCRIPTION,
    parent=shard_group,
)
RANKING_PAGE_SIZE = 5


@shard_group.command(name="top", description=ranking_messages.SHARD_TOP_DESCRIPTION)
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
        title=ranking_messages.SHARD_RANKING_TITLE,
        description=ranking_messages.shard_ranking_description(
            heading=ranking_messages.CURRENT_SHARD_RANKING_HEADING,
            trailing=AsteroidEmoji.TRANSPARENT,
        ),
        page_size=RANKING_PAGE_SIZE,
    )
    paginator = LayoutPaginator(pages=pages, use_default_buttons=False, loop_pages=False, show_disabled=True)
    paginator.add_button(
        PaginatorButton("prev", label=common_messages.PREVIOUS_PAGE_LABEL, style=discord.ButtonStyle.green)
    )
    paginator.add_button(PaginatorButton("page_indicator", style=discord.ButtonStyle.gray))
    paginator.add_button(
        PaginatorButton("next", label=common_messages.NEXT_PAGE_LABEL, style=discord.ButtonStyle.green)
    )
    await paginator.respond(interaction)


@shard_group.command(name="xp_boost", description=reward_messages.XP_BOOST_DESCRIPTION)
async def xp_boost(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    xp_boosts = await bot.db.xp_boosts.get_xp_boosts()
    if len(xp_boosts) == 0:
        logger.debug(
            "XPブースト一覧を表示しました: command=/shard xp_boost "
            f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
            f"user_id={interaction.user.id} result_count=0"
        )
        await interaction.response.send_message(reward_messages.NO_XP_BOOST)
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
                reward_messages.xp_boost_entry(
                    name=boost.name,
                    role_mention=role.mention if role else common_messages.ROLE_NOT_FOUND,
                    boost_amount=boost.boost_amount,
                    end_time=discord.utils.format_dt(boost.boost_end_time, "f")
                    if boost.boost_end_time
                    else reward_messages.UNLIMITED,
                )
            )
        pages.append(build_text_container(reward_messages.xp_boost_list(entries=entries)))
    paginator = LayoutPaginator(pages=pages, use_default_buttons=False, loop_pages=False, show_disabled=False)
    paginator.add_button(
        PaginatorButton("prev", label=common_messages.PREVIOUS_PAGE_LABEL, style=discord.ButtonStyle.green)
    )
    paginator.add_button(PaginatorButton("page_indicator", style=discord.ButtonStyle.gray, disabled=True))
    paginator.add_button(
        PaginatorButton("next", label=common_messages.NEXT_PAGE_LABEL, style=discord.ButtonStyle.green)
    )
    await paginator.respond(interaction)


@reward_group.command(name="grade", description=reward_messages.GRADE_REWARD_DESCRIPTION)
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
        entries.append(
            reward_messages.grade_reward_entry(
                grade=grade_role.grade,
                role_mention=role.mention if role else common_messages.ROLE_NOT_FOUND,
            )
        )
    await interaction.response.send_message(
        view=build_text_view(
            reward_messages.grade_reward_list(entries=entries),
            accent_color=AsteroidColor.INFO,
        )
    )


@reward_group.command(name="prestige", description=reward_messages.PRESTIGE_REWARD_DESCRIPTION)
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
        entries.append(
            reward_messages.prestige_reward_entry(
                prestige=prestige_role.prestige,
                role_mention=role.mention if role else common_messages.ROLE_NOT_FOUND,
            )
        )
    await interaction.response.send_message(
        view=build_text_view(
            reward_messages.prestige_reward_list(entries=entries),
            accent_color=AsteroidColor.INFO,
        )
    )


def register_shard_commands(bot: AsteroidBot) -> None:
    register_group(bot, shard_group)


async def setup(bot: AsteroidBot) -> None:
    register_shard_commands(bot)
