from __future__ import annotations

import discord

from app.common.constants import AsteroidColor
from app.common.discord_types import as_messageable
from app.common.guild_scope import GuildScopedLayoutView
from app.common.utils import humanize_number
from app.core.bot import AsteroidBot
from app.database.repositories.leveling_hotness import LevelingHotnessRankingData
from app.database.repositories.monthly_powers import MonthlyPowerData, MonthlyPowerRankingData
from app.database.repositories.star_grades import StarGradeData, StarGradeRankingData
from app.features.leveling.domain.math_calculation import next_grade_progress, total_shard_amount

from .messages import common as common_messages
from .messages import progression as progression_messages
from .messages import ranking as ranking_messages


class LevelingLayoutView(GuildScopedLayoutView):
    def __init__(self, *items: discord.ui.Item[GuildScopedLayoutView], timeout: float | None = 300) -> None:
        super().__init__(timeout=timeout)
        for item in items:
            self.add_item(item)


def total_monthly_power(monthly_power: MonthlyPowerData | MonthlyPowerRankingData) -> int:
    return monthly_power.text_power + monthly_power.voice_power + monthly_power.action_power


def format_ranking_position(ranking: int) -> str:
    return common_messages.ranking_position(ranking=ranking)


def build_text_container(
    content: str,
    *,
    accent_color: discord.Color | int = AsteroidColor.INFO,
) -> discord.ui.Container:
    return discord.ui.Container(discord.ui.TextDisplay(content), accent_color=accent_color)


def build_text_view(
    content: str,
    *,
    accent_color: discord.Color | int = AsteroidColor.INFO,
    timeout: float | None = 300,
) -> LevelingLayoutView:
    return LevelingLayoutView(build_text_container(content, accent_color=accent_color), timeout=timeout)


def build_user_view(
    user: discord.abc.User,
    content: str,
    *,
    accent_color: discord.Color | int = AsteroidColor.INFO,
    notice: str | None = None,
) -> LevelingLayoutView:
    children: list[discord.ui.Item[GuildScopedLayoutView]] = []
    if notice:
        children.append(discord.ui.TextDisplay(notice))
        children.append(discord.ui.Separator())
    children.append(
        discord.ui.Section(
            discord.ui.TextDisplay(content),
            accessory=discord.ui.Thumbnail(str(user.display_avatar.url)),
        )
    )
    return LevelingLayoutView(discord.ui.Container(*children, accent_color=accent_color))


async def send_grade_up_message(
    channel: discord.abc.Messageable,
    author: discord.User | discord.Member,
    grade: int,
    grade_up_amount: int,
) -> None:
    if isinstance(channel, discord.StageChannel):
        return
    await channel.send(
        embed=discord.Embed(
            title=progression_messages.LEVEL_UP_TITLE,
            description=progression_messages.grade_up(
                author_mention=author.mention,
                old_grade=grade - grade_up_amount,
                new_grade=grade,
            ),
            color=discord.Color.random(),
        )
    )


async def send_prestige_up_message(
    channel: discord.abc.Messageable,
    author: discord.User | discord.Member,
    prestige: int,
    prestige_amount: int,
) -> None:
    if isinstance(channel, discord.StageChannel):
        return
    await channel.send(
        embed=discord.Embed(
            title=progression_messages.PRESTIGE_UP_TITLE,
            description=progression_messages.prestige_up(
                author_mention=author.mention,
                old_prestige=prestige - prestige_amount,
                new_prestige=prestige,
            ),
            color=discord.Color.random(),
        )
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
    channel = as_messageable(bot.get_channel(prestige_announce_channel_id))
    if channel is None or not bot.is_operating_channel(channel):
        return
    achievement = prestige_role.mention if prestige_role else progression_messages.prestige_name(prestige=prestige)
    await channel.send(
        embed=discord.Embed(
            title=progression_messages.PRESTIGE_ACHIEVEMENT_TITLE,
            description=progression_messages.prestige_achievement(
                member_mention=member.mention,
                achievement=achievement,
            ),
            color=AsteroidColor.SUCCESS,
        )
    )


def build_star_grade_view(
    user: discord.abc.User,
    star_grade: StarGradeData | StarGradeRankingData,
    *,
    notice: str | None = None,
) -> LevelingLayoutView:
    grade_progress, grade_progress_bar = next_grade_progress(star_grade.grade, star_grade.shard)
    content = ranking_messages.star_grade_details(
        display_name=user.display_name,
        ranking=star_grade.ranking if isinstance(star_grade, StarGradeRankingData) else None,
        next_grade=star_grade.grade + 1,
        grade_progress_bar=grade_progress_bar,
        grade_progress=grade_progress,
        prestige=format_prestige_num(star_grade.prestige),
        grade=star_grade.grade,
        shard=humanize_number(star_grade.shard),
        text_shard=humanize_number(star_grade.text_shard),
        voice_shard=humanize_number(star_grade.voice_shard),
        bonus_shard=humanize_number(star_grade.bonus_shard),
    )
    return build_user_view(user, content, notice=notice)


def build_shard_ranking_pages(
    bot: AsteroidBot,
    star_grades: list[StarGradeRankingData],
    *,
    title: str,
    description: str,
    page_size: int = 10,
) -> list[discord.ui.Container]:
    pages: list[discord.ui.Container] = []
    chunks = [star_grades[index : index + page_size] for index in range(0, len(star_grades), page_size)] or [[]]
    for chunk in chunks:
        children: list[discord.ui.Item[GuildScopedLayoutView]] = [
            discord.ui.TextDisplay(common_messages.ranking_header(title=title, description=description))
        ]
        for star_grade in chunk:
            user = bot.get_user(star_grade.user_id)
            display_name = user.display_name if user else common_messages.unknown_member(user_id=star_grade.user_id)
            total_shards = total_shard_amount(star_grade.prestige, star_grade.grade, star_grade.shard)
            content = ranking_messages.shard_ranking_entry(
                ranking=format_ranking_position(star_grade.ranking),
                display_name=display_name,
                prestige=format_prestige_num(star_grade.prestige),
                grade=star_grade.grade,
                shard=humanize_number(star_grade.shard),
                total_shards=humanize_number(total_shards),
            )
            if len(children) > 1:
                children.append(discord.ui.Separator())
            if user is None:
                children.append(discord.ui.TextDisplay(content))
            else:
                children.append(
                    discord.ui.Section(
                        discord.ui.TextDisplay(content),
                        accessory=discord.ui.Thumbnail(str(user.display_avatar.url)),
                    )
                )
        if not chunk:
            children.append(discord.ui.TextDisplay(common_messages.RANKING_NO_DATA))
        pages.append(discord.ui.Container(*children, accent_color=AsteroidColor.LIGHT_BLUE))
    return pages


def build_power_view(
    user: discord.abc.User,
    monthly_power: MonthlyPowerData | MonthlyPowerRankingData,
) -> LevelingLayoutView:
    return build_user_view(
        user,
        ranking_messages.power_details(
            display_name=user.display_name,
            ranking=monthly_power.ranking if isinstance(monthly_power, MonthlyPowerRankingData) else None,
            text_power=humanize_number(monthly_power.text_power),
            voice_power=humanize_number(monthly_power.voice_power),
            action_power=humanize_number(monthly_power.action_power),
        ),
    )


def build_power_ranking_pages(
    bot: AsteroidBot,
    monthly_powers: list[MonthlyPowerRankingData],
    *,
    title: str,
    description: str,
    page_size: int = 10,
    show_header: bool = True,
) -> list[discord.ui.Container]:
    pages: list[discord.ui.Container] = []
    chunks = [monthly_powers[index : index + page_size] for index in range(0, len(monthly_powers), page_size)] or [[]]
    for chunk in chunks:
        children: list[discord.ui.Item[GuildScopedLayoutView]] = []
        if show_header:
            children.append(
                discord.ui.TextDisplay(common_messages.ranking_header(title=title, description=description))
            )
        for index, monthly_power in enumerate(chunk):
            user = bot.get_user(monthly_power.user_id)
            display_name = user.display_name if user else common_messages.unknown_member(user_id=monthly_power.user_id)
            content = ranking_messages.power_ranking_entry(
                ranking=format_ranking_position(monthly_power.ranking),
                display_name=display_name,
                text_power=humanize_number(monthly_power.text_power),
                voice_power=humanize_number(monthly_power.voice_power),
                action_power=humanize_number(monthly_power.action_power),
                total_power=humanize_number(total_monthly_power(monthly_power)),
            )
            if index > 0:
                children.append(discord.ui.Separator())
            if user is None:
                children.append(discord.ui.TextDisplay(content))
            else:
                children.append(
                    discord.ui.Section(
                        discord.ui.TextDisplay(content),
                        accessory=discord.ui.Thumbnail(str(user.display_avatar.url)),
                    )
                )
        if not chunk:
            children.append(discord.ui.TextDisplay(common_messages.RANKING_NO_DATA))
        pages.append(discord.ui.Container(*children, accent_color=AsteroidColor.PURPLE))
    return pages


def build_hotness_ranking_container(
    bot: AsteroidBot,
    rankings: list[LevelingHotnessRankingData],
    *,
    title: str,
    description: str,
) -> discord.ui.Container:
    children: list[discord.ui.Item[GuildScopedLayoutView]] = [
        discord.ui.TextDisplay(common_messages.ranking_header(title=title, description=description))
    ]
    for ranking, hotness in enumerate(rankings, start=1):
        user = bot.get_user(hotness.user_id)
        display_name = user.display_name if user else common_messages.unknown_member(user_id=hotness.user_id)
        content = ranking_messages.hotness_ranking_entry(
            ranking=format_ranking_position(ranking),
            display_name=display_name,
            hotness=humanize_number(hotness.hotness),
        )
        if len(children) > 1:
            children.append(discord.ui.Separator())
        if user is None:
            children.append(discord.ui.TextDisplay(content))
        else:
            children.append(
                discord.ui.Section(
                    discord.ui.TextDisplay(content),
                    accessory=discord.ui.Thumbnail(str(user.display_avatar.url)),
                )
            )
    if not rankings:
        children.append(discord.ui.TextDisplay(common_messages.RANKING_NO_DATA))
    return discord.ui.Container(*children, accent_color=AsteroidColor.ORANGE)


def build_rank_view(
    user: discord.abc.User,
    monthly_power: MonthlyPowerRankingData,
    star_grade: StarGradeRankingData,
) -> LevelingLayoutView:
    grade_progress, grade_progress_bar = next_grade_progress(star_grade.grade, star_grade.shard)
    total_shards = total_shard_amount(star_grade.prestige, star_grade.grade, star_grade.shard)
    total_power = total_monthly_power(monthly_power)
    return build_user_view(
        user,
        ranking_messages.rank_card(
            display_name=user.display_name,
            grade_progress_bar=grade_progress_bar,
            grade_progress=grade_progress,
            total_shards=humanize_number(total_shards),
            shard_ranking=star_grade.ranking,
            prestige=format_prestige_num(star_grade.prestige),
            grade=star_grade.grade,
            shard=humanize_number(star_grade.shard),
            text_shard=humanize_number(star_grade.text_shard),
            voice_shard=humanize_number(star_grade.voice_shard),
            bonus_shard=humanize_number(star_grade.bonus_shard),
            total_power=humanize_number(total_power),
            power_ranking=monthly_power.ranking,
            text_power=humanize_number(monthly_power.text_power),
            voice_power=humanize_number(monthly_power.voice_power),
            action_power=humanize_number(monthly_power.action_power),
        ),
    )


def format_prestige_num(prestige: int) -> str:
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    roman_numeral = ""
    index = 0
    if prestige == 0:
        return "-"
    while prestige > 0:
        for _ in range(prestige // val[index]):
            roman_numeral += syms[index]
            prestige -= val[index]
        index += 1
    return roman_numeral if index > 0 else "0"
