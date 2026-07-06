from __future__ import annotations

from logging import getLogger

import discord
from discord import app_commands

from app.common.command_groups import get_bot, register_group
from app.common.constants import AsteroidEmoji
from app.common.layout_pages import LayoutPaginator
from app.common.pages import PaginatorButton
from app.core.bot import AsteroidBot
from app.features.leveling.build_send_message import build_power_ranking_pages

logger = getLogger(__name__)

power_group = app_commands.Group(name="power", description="月間ランキング系コマンド")
RANKING_PAGE_SIZE = 5


@power_group.command(name="top", description="現在のパワーランキングを表示します")
async def top(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    monthly_powers = await bot.db.monthly_powers.get_monthly_power_ranking()
    logger.debug(
        "パワーランキングを表示しました: command=/power top "
        f"guild_id={interaction.guild_id} channel_id={interaction.channel_id} "
        f"user_id={interaction.user.id} result_count={len(monthly_powers)}"
    )
    pages = build_power_ranking_pages(
        bot,
        monthly_powers,
        title="パワーランキング",
        description=(
            "現在のパワーランキングを表示します\n\n"
            f"{AsteroidEmoji.TEXT_POWER}: テキストパワー\n"
            f"{AsteroidEmoji.VOICE_POWER}: ボイスパワー\n"
            f"{AsteroidEmoji.ACTION_POWER}: アクションパワー\n"
            f"{AsteroidEmoji.TRANSPARENT}"
        ),
        page_size=RANKING_PAGE_SIZE,
    )
    paginator = LayoutPaginator(pages=pages, use_default_buttons=False, loop_pages=False, show_disabled=True)
    paginator.add_button(PaginatorButton("prev", label="<", style=discord.ButtonStyle.green))
    paginator.add_button(PaginatorButton("page_indicator", style=discord.ButtonStyle.gray))
    paginator.add_button(PaginatorButton("next", label=">", style=discord.ButtonStyle.green))
    await paginator.respond(interaction)


def register_power_commands(bot: AsteroidBot) -> None:
    register_group(bot, power_group)


async def setup(bot: AsteroidBot) -> None:
    register_power_commands(bot)
