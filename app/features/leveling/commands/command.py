from __future__ import annotations

import json
import os.path

import aiohttp
import discord
from discord import app_commands

from app.common.command_groups import get_bot, register_command, register_setup_command
from app.core.bot import AsteroidBot
from app.features.leveling.build_send_message import build_rank_embed, send_prestige_announce
from app.features.leveling.manage_reward_role import sync_grade_prestige_role
from app.features.leveling.service import (
    apply_voice_xp_claim_side_effects,
    build_voice_xp_claim_message,
    claim_voice_xp_rewards,
)


@app_commands.command(name="claim_voice_xp", description="VC経験値を獲得します")
async def claim_voice_xp(interaction: discord.Interaction) -> None:
    bot = get_bot(interaction)
    await interaction.response.defer()
    claim_result = await claim_voice_xp_rewards(bot, interaction.user.id)
    if claim_result is None:
        await interaction.followup.send("VC経験値を獲得していません")
        return

    await interaction.followup.send(build_voice_xp_claim_message(interaction.user, claim_result))
    await apply_voice_xp_claim_side_effects(bot, interaction.channel, interaction.user, claim_result)


@app_commands.command(name="rank", description="自分の順位を表示します")
@app_commands.describe(user="順位を表示するユーザー")
async def rank(interaction: discord.Interaction, user: discord.User | None = None) -> None:
    bot = get_bot(interaction)
    user = user or interaction.user
    monthly_power = await bot.db.monthly_powers.get_monthly_power_ranking(user.id)
    if monthly_power is None:
        await interaction.response.send_message(f"{user.display_name}はまだパワーを獲得していません")
        return
    star_grade = await bot.db.star_grades.get_star_grade_ranking(user.id)
    if star_grade is None:
        await interaction.response.send_message(f"{user.display_name}はまだシャードを獲得していません")
        return
    await interaction.response.send_message(embed=build_rank_embed(user, monthly_power, star_grade))


@app_commands.command(name="transfer_mee6", description="MEE6から移行する")
@app_commands.describe(
    sync_role="グレード・プレステージロールを同期するか", prestige_announce="プレステージアナウンスを行うか"
)
async def transfer_mee6(interaction: discord.Interaction, sync_role: bool, prestige_announce: bool) -> None:
    bot = get_bot(interaction)
    await interaction.response.send_message("データ取得中...")

    if os.path.exists("mee6_data.json"):
        with open("mee6_data.json", encoding="utf-8") as f:
            data = json.load(f)
    else:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://mee6.xyz/api/plugins/levels/leaderboard/705003456984907786?limit=500"
            ) as response:
                if response.status != 200:
                    await interaction.followup.send("MEE6からのデータ取得に失敗しました")
                    return
                data = await response.json()
                with open("mee6_data.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)

    await interaction.edit_original_response(
        content="データ取得完了、データベースに登録しています..."
        + ("\nロールの同期が有効です、通常より時間がかかります..." if sync_role else "")
        + ("\nプレステージアナウンスが有効です、通常より時間がかかります..." if prestige_announce else "")
    )

    prestige_roles = bot.config["prestige_roles_id_list"]
    prestige_roles_id = [int(prestige_role["role_id"]) for prestige_role in prestige_roles]

    for player in data["players"]:
        user_id = int(player["id"])
        xp = player["xp"]
        member = interaction.guild.get_member(user_id)
        if xp < 13800 and member is None:
            continue

        star_grade = await bot.db.star_grades.get_star_grade(user_id) or await bot.db.star_grades.create_star_grade(
            user_id
        )
        if member:
            prestige_amount = sum(
                1
                for prestige_role_id in prestige_roles_id
                if interaction.guild.get_role(prestige_role_id) in member.roles
            )
            if prestige_amount > 0:
                star_grade, _, _, _ = await bot.db.star_grades.add_prestige(star_grade, prestige_amount, "テキスト")

        star_grade, _, prestige_amount = await bot.db.star_grades.add_text_shard(star_grade, xp)
        if prestige_amount > 0 and member and prestige_announce:
            await send_prestige_announce(bot, member, star_grade.prestige)
        if sync_role and member:
            await sync_grade_prestige_role(bot, member, star_grade)

    await interaction.followup.send(
        "移行が完了しました"
        + ("\nロールの同期を行いました" if sync_role else "")
        + ("\nプレステージアナウンスを行いました" if prestige_announce else "")
    )


async def setup(bot: AsteroidBot) -> None:
    register_command(bot, claim_voice_xp)
    register_command(bot, rank)
    register_setup_command(bot, transfer_mee6)
