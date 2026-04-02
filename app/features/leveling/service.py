from __future__ import annotations

from dataclasses import dataclass
from logging import getLogger

import discord

from app.common.utils import humanize_number
from app.core.bot import AsteroidBot
from app.database.repositories.star_grades import StarGradeData
from app.database.repositories.voice_xp_limits import VoiceXPLimitData
from app.features.leveling.build_send_message import (
    send_grade_up_message,
    send_prestige_announce,
    send_prestige_up_message,
)
from app.features.leveling.manage_reward_role import sync_grade_prestige_role

logger = getLogger(__name__)


@dataclass(slots=True)
class VoiceXPClaimResult:
    voice_xp_limit: VoiceXPLimitData
    star_grade: StarGradeData
    grade_up_amount: int
    prestige_amount: int


async def claim_voice_xp_rewards(bot: AsteroidBot, user_id: int) -> VoiceXPClaimResult | None:
    async with bot.db.session() as session:
        voice_xp_limit = await bot.db.voice_xp_limits.get_voice_xp_limit_lock(session, user_id)
        if (
            voice_xp_limit is None
            or (voice_xp_limit.voice_shard + voice_xp_limit.bonus_shard + voice_xp_limit.voice_power) < 1
        ):
            logger.debug(f"VC経験値受け取り対象がありません: user_id={user_id}")
            return None

        monthly_power = await bot.db.monthly_powers.get_monthly_power_lock(
            session, user_id
        ) or await bot.db.monthly_powers.create_monthly_power_lock(session, user_id)
        if voice_xp_limit.voice_power > 0:
            await bot.db.monthly_powers.add_voice_power_lock(session, monthly_power, voice_xp_limit.voice_power)

        star_grade = await bot.db.star_grades.get_star_grade_lock(
            session, user_id
        ) or await bot.db.star_grades.create_star_grade_lock(session, user_id)
        grade_up_amount = 0
        prestige_amount = 0

        if voice_xp_limit.voice_shard > 0:
            star_grade, grade_up_amount_voice, prestige_amount_voice = await bot.db.star_grades.add_voice_shard_lock(
                session, star_grade, voice_xp_limit.voice_shard
            )
            grade_up_amount += grade_up_amount_voice
            prestige_amount += prestige_amount_voice

        if voice_xp_limit.bonus_shard > 0:
            star_grade, grade_up_amount_bonus, prestige_amount_bonus = await bot.db.star_grades.add_bonus_shard_lock(
                session, star_grade, voice_xp_limit.bonus_shard
            )
            grade_up_amount += grade_up_amount_bonus
            prestige_amount += prestige_amount_bonus

        await bot.db.voice_xp_limits.delete_voice_xp_limit_lock(session, user_id)
        await session.commit()

    logger.debug(
        f"VC経験値を受け取りました: user_id={user_id} voice_shard={voice_xp_limit.voice_shard} "
        f"bonus_shard={voice_xp_limit.bonus_shard} voice_power={voice_xp_limit.voice_power} "
        f"grade_up={grade_up_amount} prestige_up={prestige_amount}"
    )
    return VoiceXPClaimResult(
        voice_xp_limit=voice_xp_limit,
        star_grade=star_grade,
        grade_up_amount=grade_up_amount,
        prestige_amount=prestige_amount,
    )


def build_voice_xp_claim_message(
    user: discord.User | discord.Member,
    claim_result: VoiceXPClaimResult,
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
    claim_result: VoiceXPClaimResult,
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
