from __future__ import annotations

import discord
from discord import app_commands

from app.common.command_groups import get_bot, register_group
from app.common.constants import AsteroidColor, AsteroidEmoji
from app.common.pages import Paginator, PaginatorButton
from app.core.bot import AsteroidBot
from app.features.leveling.build_send_message import build_power_ranking_embed

power_group = app_commands.Group(name="power", description="月間ランキング系コマンド")


@power_group.command(name="top", description="現在のパワーランキングを表示します")
async def top(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    monthly_powers = await bot.db.monthly_powers.get_monthly_power_ranking()
    base_embed = discord.Embed(
        title="パワーランキング",
        description="現在のパワーランキングを表示します\n\n"
        f"{AsteroidEmoji.TEXT_POWER}: テキストパワー\n"
        f"{AsteroidEmoji.VOICE_POWER}: ボイスパワー\n"
        f"{AsteroidEmoji.ACTION_POWER}: アクションパワー\n"
        f"{AsteroidEmoji.TRANSPARENT}",
        color=AsteroidColor.INFO,
    )
    embeds = build_power_ranking_embed(bot, monthly_powers, base_embed)
    paginator = Paginator(pages=embeds, use_default_buttons=False, loop_pages=False, show_disabled=False)
    paginator.add_button(PaginatorButton("prev", label="<", style=discord.ButtonStyle.green))
    paginator.add_button(PaginatorButton("page_indicator", style=discord.ButtonStyle.gray, disabled=True))
    paginator.add_button(PaginatorButton("next", label=">", style=discord.ButtonStyle.green))
    await paginator.respond(interaction)


def register_power_commands(bot: AsteroidBot) -> None:
    register_group(bot, power_group)


async def setup(bot: AsteroidBot) -> None:
    register_power_commands(bot)
