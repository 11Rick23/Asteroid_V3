from __future__ import annotations

from logging import getLogger

import discord

from app.common.utils import humanize_number
from app.core.bot import AsteroidBot
from app.database.repositories.leveling import VoiceXPClaimData
from app.features.leveling.build_send_message import (
    send_grade_up_message,
    send_prestige_announce,
    send_prestige_up_message,
)
from app.features.leveling.manage_reward_role import sync_grade_prestige_role

logger = getLogger(__name__)


async def claim_voice_xp_rewards(bot: AsteroidBot, user_id: int) -> VoiceXPClaimData | None:
    claim_result = await bot.db.leveling.claim_voice_xp(user_id)
    if claim_result is None:
        logger.debug(f"VC経験値受け取り対象がありません: user_id={user_id}")
        return None

    logger.debug(
        f"VC経験値を受け取りました: user_id={user_id} voice_shard={claim_result.voice_xp_limit.voice_shard} "
        f"bonus_shard={claim_result.voice_xp_limit.bonus_shard} "
        f"voice_power={claim_result.voice_xp_limit.voice_power} "
        f"grade_up={claim_result.grade_up_amount} prestige_up={claim_result.prestige_amount}"
    )
    return claim_result


def build_voice_xp_claim_message(
    user: discord.User | discord.Member,
    claim_result: VoiceXPClaimData,
) -> str:
    return (
        f"{user.mention} ボイスシャードを`{humanize_number(claim_result.voice_xp_limit.voice_shard)}`獲得しました\n"
        f"ボイスパワーを`{humanize_number(claim_result.voice_xp_limit.voice_power)}`獲得しました\n"
        f"ボイスボーナスシャードを`{humanize_number(claim_result.voice_xp_limit.bonus_shard)}`獲得しました"
    )


async def apply_voice_xp_claim_side_effects(
    bot: AsteroidBot,
    channel: discord.abc.Messageable | None,
    user: discord.User | discord.Member,
    claim_result: VoiceXPClaimData,
) -> None:
    if channel is not None:
        if claim_result.prestige_amount > 0:
            await send_prestige_up_message(
                channel,
                user,
                claim_result.star_grade.prestige,
                claim_result.prestige_amount,
            )
            if isinstance(user, discord.Member):
                await send_prestige_announce(bot, user, claim_result.star_grade.prestige)
        elif claim_result.grade_up_amount > 0:
            await send_grade_up_message(
                channel,
                user,
                claim_result.star_grade.grade,
                claim_result.grade_up_amount,
            )

    if isinstance(user, discord.Member):
        await sync_grade_prestige_role(bot, user, claim_result.star_grade)
