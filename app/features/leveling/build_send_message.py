from __future__ import annotations

import discord

from app.common.constants import AsteroidColor, AsteroidEmoji
from app.common.discord_types import as_messageable
from app.common.guild_scope import GuildScopedLayoutView
from app.common.utils import humanize_number
from app.core.bot import AsteroidBot
from app.database.repositories.leveling_hotness import LevelingHotnessRankingData
from app.database.repositories.monthly_powers import MonthlyPowerData, MonthlyPowerRankingData
from app.database.repositories.star_grades import StarGradeData, StarGradeRankingData
from app.features.leveling.domain.math_calculation import next_grade_progress, total_shard_amount


class LevelingLayoutView(GuildScopedLayoutView):
    def __init__(self, *items: discord.ui.Item[GuildScopedLayoutView], timeout: float | None = 300) -> None:
        super().__init__(timeout=timeout)
        for item in items:
            self.add_item(item)


def total_monthly_power(monthly_power: MonthlyPowerData | MonthlyPowerRankingData) -> int:
    return monthly_power.text_power + monthly_power.voice_power + monthly_power.action_power


def format_ranking_position(ranking: int) -> str:
    medals = ("🥇", "🥈", "🥉")
    return medals[ranking - 1] if 1 <= ranking <= len(medals) else f"{ranking}位"


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
        view=build_text_view(
            "# レベルアップ！\n"
            f"**{author.mention}さんがGrade. {grade - grade_up_amount}からGrade. {grade}へグレードアップ！**",
            accent_color=discord.Color.random(),
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
        view=build_text_view(
            "# プレステージ！\n"
            f"**{author.mention}さんがPrestige. {prestige - prestige_amount}から"
            f"Prestige. {prestige}へプレステージ！**",
            accent_color=discord.Color.random(),
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
    achievement = prestige_role.mention if prestige_role else f"プレステージ{prestige}"
    await channel.send(
        view=build_user_view(
            member,
            f"# プレステージ達成！\n{member.mention}さんが{achievement}を達成しました！\nおめでとうございます！",
            accent_color=AsteroidColor.SUCCESS,
        )
    )


def build_star_grade_view(
    user: discord.abc.User,
    star_grade: StarGradeData | StarGradeRankingData,
    *,
    notice: str | None = None,
) -> LevelingLayoutView:
    grade_progress, grade_progress_bar = next_grade_progress(star_grade.grade, star_grade.shard)
    ranking = f"現在の順位: {star_grade.ranking}位\n\n" if isinstance(star_grade, StarGradeRankingData) else ""
    content = (
        f"# {user.display_name}のシャード\n"
        f"{ranking}"
        f"{AsteroidEmoji.GRADE}Grade. {star_grade.grade + 1}までの進捗ケージ\n"
        f"## {grade_progress_bar} {grade_progress}%\n\n"
        f"### プレステージ数\n{AsteroidEmoji.PRESTIGE} {format_prestige_num(star_grade.prestige)}\n"
        f"### グレード数\n{AsteroidEmoji.GRADE} {star_grade.grade}\n"
        f"### シャード数\n{AsteroidEmoji.SHARD} {humanize_number(star_grade.shard)}\n"
        f"### 累計テキストシャード数\n{AsteroidEmoji.TEXT_SHARD} {humanize_number(star_grade.text_shard)}\n"
        f"### 累計ボイスシャード数\n{AsteroidEmoji.VOICE_SHARD} {humanize_number(star_grade.voice_shard)}\n"
        f"### 累計ボーナスシャード\n{AsteroidEmoji.BONUS_SHARD} {humanize_number(star_grade.bonus_shard)}"
    )
    return build_user_view(user, content, notice=notice)


def build_shard_ranking_pages(
    bot: AsteroidBot,
    star_grades: list[StarGradeRankingData],
    *,
    title: str,
    description: str,
) -> list[discord.ui.Container]:
    pages: list[discord.ui.Container] = []
    chunks = [star_grades[index : index + 10] for index in range(0, len(star_grades), 10)] or [[]]
    for chunk in chunks:
        children: list[discord.ui.Item[GuildScopedLayoutView]] = [discord.ui.TextDisplay(f"# {title}\n{description}")]
        for star_grade in chunk:
            user = bot.get_user(star_grade.user_id)
            display_name = user.display_name if user else f"不明なメンバー [{star_grade.user_id}]"
            total_shards = total_shard_amount(star_grade.prestige, star_grade.grade, star_grade.shard)
            content = (
                f"### {format_ranking_position(star_grade.ranking)}: {display_name}\n"
                f"{AsteroidEmoji.PRESTIGE} {format_prestige_num(star_grade.prestige)}"
                f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.GRADE} {star_grade.grade}"
                f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.SHARD} {humanize_number(star_grade.shard)}\n"
                f"合計: {humanize_number(total_shards)}"
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
            children.append(discord.ui.TextDisplay("ランキングデータはありません。"))
        pages.append(discord.ui.Container(*children, accent_color=AsteroidColor.LIGHT_BLUE))
    return pages


def build_power_view(
    user: discord.abc.User,
    monthly_power: MonthlyPowerData | MonthlyPowerRankingData,
) -> LevelingLayoutView:
    ranking = (
        f"現在の順位: {monthly_power.ranking}位\n\n" if isinstance(monthly_power, MonthlyPowerRankingData) else ""
    )
    return build_user_view(
        user,
        f"# {user.display_name}のパワー\n"
        f"{ranking}"
        f"### テキストパワー数\n{AsteroidEmoji.TEXT_POWER} {humanize_number(monthly_power.text_power)}\n"
        f"### ボイスパワー数\n{AsteroidEmoji.VOICE_POWER} {humanize_number(monthly_power.voice_power)}\n"
        f"### アクションパワー数\n{AsteroidEmoji.ACTION_POWER} {humanize_number(monthly_power.action_power)}",
    )


def build_power_ranking_pages(
    bot: AsteroidBot,
    monthly_powers: list[MonthlyPowerRankingData],
    *,
    title: str,
    description: str,
) -> list[discord.ui.Container]:
    pages: list[discord.ui.Container] = []
    chunks = [monthly_powers[index : index + 10] for index in range(0, len(monthly_powers), 10)] or [[]]
    for chunk in chunks:
        children: list[discord.ui.Item[GuildScopedLayoutView]] = [discord.ui.TextDisplay(f"# {title}\n{description}")]
        for monthly_power in chunk:
            user = bot.get_user(monthly_power.user_id)
            display_name = user.display_name if user else f"不明なメンバー [{monthly_power.user_id}]"
            content = (
                f"### {format_ranking_position(monthly_power.ranking)}: {display_name}\n"
                f"{AsteroidEmoji.TEXT_POWER} {humanize_number(monthly_power.text_power)}"
                f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.VOICE_POWER} "
                f"{humanize_number(monthly_power.voice_power)}"
                f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.ACTION_POWER} "
                f"{humanize_number(monthly_power.action_power)}\n"
                f"合計: {humanize_number(total_monthly_power(monthly_power))}"
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
            children.append(discord.ui.TextDisplay("ランキングデータはありません。"))
        pages.append(discord.ui.Container(*children, accent_color=AsteroidColor.PURPLE))
    return pages


def build_hotness_ranking_container(
    bot: AsteroidBot,
    rankings: list[LevelingHotnessRankingData],
    *,
    title: str,
    description: str,
) -> discord.ui.Container:
    children: list[discord.ui.Item[GuildScopedLayoutView]] = [discord.ui.TextDisplay(f"# {title}\n{description}")]
    for ranking, hotness in enumerate(rankings, start=1):
        user = bot.get_user(hotness.user_id)
        display_name = user.display_name if user else f"不明なメンバー [{hotness.user_id}]"
        content = (
            f"### {format_ranking_position(ranking)}: {display_name}\n🔥 {humanize_number(hotness.hotness)}"
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
        children.append(discord.ui.TextDisplay("ランキングデータはありません。"))
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
        f"# {user.display_name}のランクカード\n"
        f"次のグレードまで…\n## {grade_progress_bar} {grade_progress}%\n"
        f"### {humanize_number(total_shards)}シャード - 現在{star_grade.ranking}位\n"
        f"{AsteroidEmoji.PRESTIGE} {format_prestige_num(star_grade.prestige)}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.GRADE} {star_grade.grade}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.SHARD} {humanize_number(star_grade.shard)}\n"
        f"{AsteroidEmoji.TEXT_SHARD} {humanize_number(star_grade.text_shard)}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.VOICE_SHARD} {humanize_number(star_grade.voice_shard)}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.BONUS_SHARD} {humanize_number(star_grade.bonus_shard)}\n\n"
        f"### {humanize_number(total_power)}パワー - 現在{monthly_power.ranking}位\n"
        f"{AsteroidEmoji.TEXT_POWER} {humanize_number(monthly_power.text_power)}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.VOICE_POWER} {humanize_number(monthly_power.voice_power)}"
        f"{AsteroidEmoji.TRANSPARENT}{AsteroidEmoji.ACTION_POWER} {humanize_number(monthly_power.action_power)}",
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
