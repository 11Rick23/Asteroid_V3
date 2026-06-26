from __future__ import annotations

from datetime import datetime
from logging import getLogger

from app.common.constants import AsteroidColor
from app.common.discord_types import as_messageable
from app.common.utils import generate_timestamp
from app.core.bot import AsteroidBot
from app.database.repositories.monthly_powers import MonthlyPowerRankingData

from .action_power import build_accumulated_action_power_message
from .build_send_message import LevelingLayoutView, build_power_ranking_pages, build_text_container

logger = getLogger(__name__)


def build_monthly_ranking_views(
    bot: AsteroidBot,
    monthly_powers: list[MonthlyPowerRankingData],
) -> tuple[LevelingLayoutView, LevelingLayoutView, LevelingLayoutView]:
    ranking_text = "\n".join(f"> ### {power.ranking}位: <@{power.user_id}>" for power in monthly_powers)
    first_half = build_power_ranking_pages(
        bot,
        monthly_powers[:5],
        title="",
        description="",
        page_size=5,
        show_header=False,
    )[0]
    second_half = build_power_ranking_pages(
        bot,
        monthly_powers[5:10],
        title="",
        description="",
        page_size=5,
        show_header=False,
    )[0]
    return (
        LevelingLayoutView(
            build_text_container(
                "# ということで、今回のtop10は...\n\n"
                f"{ranking_text or 'ランキングデータはありません。'}\n"
                "# このようになりました！おめでとうございます！",
                accent_color=AsteroidColor.SUCCESS,
            )
        ),
        LevelingLayoutView(first_half),
        LevelingLayoutView(second_half),
    )


async def run_monthly_ranking(
    bot: AsteroidBot,
    *,
    force: bool = False,
    delete_data: bool = True,
) -> int | None:
    if not bot.db.is_initialized():
        return None
    now = datetime.now()
    if not force and (now.day != 1 or now.hour != 0 or now.minute != 0):
        return None
    logger.info("月間ランキング集計を開始します。")
    guild = bot.get_guild(bot.config.discord.guild_id)
    if guild is None:
        logger.warning(f"月間ランキング集計先ギルドが見つかりませんでした: guild_id={bot.config.discord.guild_id}")
        return None
    top1_role = guild.get_role(bot.config.leveling.top1_role_id)
    top10_role = guild.get_role(bot.config.leveling.top10_role_id)
    monthly_powers = await bot.db.monthly_powers.get_monthly_power_ranking(limit=10)
    remove_top10_ids = [member.id for member in top10_role.members] if top10_role else []
    for power in monthly_powers:
        member = guild.get_member(power.user_id)
        if member is None:
            continue
        if power.ranking == 1 and top1_role is not None:
            await member.add_roles(top1_role, reason=f"[{generate_timestamp()}] 月間ランキングにより付与されました")
        if power.user_id in remove_top10_ids:
            remove_top10_ids.remove(power.user_id)
        elif top10_role is not None:
            await member.add_roles(top10_role, reason=f"[{generate_timestamp()}] 月間ランキングにより付与されました")
    for user_id in remove_top10_ids:
        member = guild.get_member(user_id)
        if member is not None and top10_role is not None:
            await member.remove_roles(
                top10_role, reason=f"[{generate_timestamp()}] 月間ランキングにより剥奪されました"
            )
    channel = as_messageable(bot.get_channel(bot.config.leveling.month_ranking_board_channel_id))
    if channel is not None and bot.is_operating_channel(channel):
        for view in build_monthly_ranking_views(bot, monthly_powers):
            await channel.send(view=view)
    action_channel = as_messageable(bot.get_channel(bot.config.leveling.action_power_channel_id))
    if action_channel is not None and bot.is_operating_channel(action_channel):
        total = await bot.db.monthly_action_powers.sum_action_power()
        await action_channel.send(build_accumulated_action_power_message(total))
    if delete_data:
        await bot.db.leveling.reset_monthly_power_state()
    logger.info(
        f"月間ランキング集計が完了しました: guild_id={guild.id} "
        f"ranked_count={len(monthly_powers)} data_deleted={delete_data}"
    )
    return len(monthly_powers)
