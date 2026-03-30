from __future__ import annotations

import discord
from discord import app_commands

from app.common.command_groups import get_bot, register_group
from app.common.constants import AsteroidColor
from app.core.bot import AsteroidBot

suggest_group = app_commands.Group(name="suggestion", description="要望に関するコマンド")


async def suggestion_handler(interaction: discord.Interaction, judge: str, reason: str) -> None:
    bot = get_bot(interaction)
    await interaction.response.defer()
    if isinstance(interaction.channel, discord.Thread):
        thread = interaction.channel
        if (
            isinstance(thread.parent, discord.ForumChannel)
            and thread.parent.id == bot.config.suggest.suggestion_forum_channel_id
        ):
            await thread.edit(archived=True)
            embed = discord.Embed(
                color=AsteroidColor.SUCCESS if judge == "可決" else AsteroidColor.WARNING,
                title=f"この要望は{judge}されました",
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.add_field(name="理由", value=reason)
            await interaction.followup.send(embed=embed)
            return

        await interaction.followup.send(
            embed=discord.Embed(
                color=AsteroidColor.WARNING,
                description="このコマンドは要望フォーラム下のスレッドにのみ使用できます。",
            ),
            ephemeral=True,
        )
        return

    await interaction.followup.send(
        embed=discord.Embed(color=AsteroidColor.WARNING, description="このコマンドはスレッドでのみ実行できます。"),
        ephemeral=True,
    )


@suggest_group.command(name="approve", description="要望を可決")
@app_commands.describe(reason="要望を可決する理由")
@app_commands.checks.has_permissions(administrator=True)
async def approve(interaction: discord.Interaction, reason: str) -> None:
    await suggestion_handler(interaction, "可決", reason)


@suggest_group.command(name="deny", description="要望を否決")
@app_commands.describe(reason="要望を否決する理由")
@app_commands.checks.has_permissions(administrator=True)
async def deny(interaction: discord.Interaction, reason: str) -> None:
    await suggestion_handler(interaction, "否決", reason)


async def setup(bot: AsteroidBot) -> None:
    register_group(bot, suggest_group)
