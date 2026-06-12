from __future__ import annotations

from dataclasses import dataclass

from app.database.repositories.monthly_action_powers import MonthlyActionPowerData
from app.database.repositories.monthly_powers import MonthlyPowerData
from app.database.repositories.star_grades import StarGradeData
from app.database.repositories.voice_xp_limits import VoiceXPLimitData


@dataclass(slots=True)
class LevelingRewardData:
    star_grade: StarGradeData
    grade_up_amount: int
    prestige_amount: int


@dataclass(slots=True)
class VoiceXPAccrualData:
    voice_xp_limit: VoiceXPLimitData
    notify_half_limit: bool
    notify_full_limit: bool


@dataclass(slots=True)
class VoiceXPClaimData:
    voice_xp_limit: VoiceXPLimitData
    star_grade: StarGradeData
    grade_up_amount: int
    prestige_amount: int


class LevelingTransactions:
    def __init__(self, db):
        self.db = db

    async def add_action_power(self, user_id: int, amount: int) -> MonthlyActionPowerData:
        async with self.db.session() as session:
            action_power = await self.db.monthly_action_powers.get_monthly_action_power_lock(
                session, user_id
            ) or await self.db.monthly_action_powers.create_monthly_action_power_lock(session, user_id)
            updated = await self.db.monthly_action_powers.add_action_power_lock(session, action_power, amount)
            if amount > 0:
                await self.db.leveling_hotness.record_gain_lock(session, user_id, amount)
            await session.commit()
            return updated

    async def add_text_power(self, user_id: int, amount: int) -> MonthlyPowerData:
        async with self.db.session() as session:
            monthly_power = await self.db.monthly_powers.get_monthly_power_lock(
                session, user_id
            ) or await self.db.monthly_powers.create_monthly_power_lock(session, user_id)
            updated = await self.db.monthly_powers.add_text_power_lock(session, monthly_power, amount)
            if amount > 0:
                await self.db.leveling_hotness.record_gain_lock(session, user_id, amount)
            await session.commit()
            return updated

    async def add_voice_power(self, user_id: int, amount: int) -> MonthlyPowerData:
        async with self.db.session() as session:
            monthly_power = await self.db.monthly_powers.get_monthly_power_lock(
                session, user_id
            ) or await self.db.monthly_powers.create_monthly_power_lock(session, user_id)
            updated = await self.db.monthly_powers.add_voice_power_lock(session, monthly_power, amount)
            if amount > 0:
                await self.db.leveling_hotness.record_gain_lock(session, user_id, amount)
            await session.commit()
            return updated

    async def remove_action_power(self, user_id: int, amount: int) -> MonthlyActionPowerData:
        async with self.db.session() as session:
            action_power = await self.db.monthly_action_powers.get_monthly_action_power_lock(
                session, user_id
            ) or await self.db.monthly_action_powers.create_monthly_action_power_lock(session, user_id)
            updated = await self.db.monthly_action_powers.remove_action_power_lock(session, action_power, amount)
            await session.commit()
            return updated

    async def apply_message_reward(
        self,
        user_id: int,
        power_amount: int,
        bonus_shard_amount: int,
    ) -> LevelingRewardData:
        async with self.db.session() as session:
            monthly_power = await self.db.monthly_powers.get_monthly_power_lock(
                session, user_id
            ) or await self.db.monthly_powers.create_monthly_power_lock(session, user_id)
            await self.db.monthly_powers.add_text_power_lock(session, monthly_power, power_amount)
            if power_amount > 0:
                await self.db.leveling_hotness.record_gain_lock(
                    session,
                    user_id,
                    power_amount,
                )

            star_grade = await self.db.star_grades.get_star_grade_lock(
                session, user_id
            ) or await self.db.star_grades.create_star_grade_lock(session, user_id)
            star_grade, text_grade_ups, text_prestige_ups = await self.db.star_grades.add_text_shard_lock(
                session, star_grade, power_amount
            )

            bonus_grade_ups = 0
            bonus_prestige_ups = 0
            if bonus_shard_amount > 0:
                (
                    star_grade,
                    bonus_grade_ups,
                    bonus_prestige_ups,
                ) = await self.db.star_grades.add_bonus_shard_lock(
                    session,
                    star_grade,
                    bonus_shard_amount,
                )

            await session.commit()
            return LevelingRewardData(
                star_grade=star_grade,
                grade_up_amount=text_grade_ups + bonus_grade_ups,
                prestige_amount=text_prestige_ups + bonus_prestige_ups,
            )

    async def accrue_voice_xp(
        self,
        user_id: int,
        *,
        voice_power_amount: int,
        voice_shard_amount: int,
        bonus_shard_amount: int,
        limit: int,
    ) -> VoiceXPAccrualData:
        async with self.db.session() as session:
            data = await self.db.voice_xp_limits.get_voice_xp_limit_lock(
                session, user_id
            ) or await self.db.voice_xp_limits.create_voice_xp_limit_lock(session, user_id)
            was_half_notified = data.half_notify
            was_full_notified = data.full_notify

            if data.voice_power < limit:
                data, _, _ = await self.db.voice_xp_limits.add_voice_power_lock(
                    session,
                    data,
                    voice_power_amount,
                    limit,
                )

            if (data.voice_shard + data.bonus_shard) < limit:
                data, _, limit_reached = await self.db.voice_xp_limits.add_voice_shard_lock(
                    session,
                    data,
                    voice_shard_amount,
                    limit,
                )
                if bonus_shard_amount > 0 and not limit_reached:
                    data, _, _ = await self.db.voice_xp_limits.add_bonus_shard_lock(
                        session,
                        data,
                        bonus_shard_amount,
                        limit,
                    )

            await session.commit()
            return VoiceXPAccrualData(
                voice_xp_limit=data,
                notify_half_limit=data.half_notify and not was_half_notified and not data.full_notify,
                notify_full_limit=data.full_notify and not was_full_notified,
            )

    async def claim_voice_xp(self, user_id: int) -> VoiceXPClaimData | None:
        async with self.db.session() as session:
            voice_xp_limit = await self.db.voice_xp_limits.get_voice_xp_limit_lock(session, user_id)
            if (
                voice_xp_limit is None
                or (voice_xp_limit.voice_shard + voice_xp_limit.bonus_shard + voice_xp_limit.voice_power) < 1
            ):
                return None

            monthly_power = await self.db.monthly_powers.get_monthly_power_lock(
                session, user_id
            ) or await self.db.monthly_powers.create_monthly_power_lock(session, user_id)
            if voice_xp_limit.voice_power > 0:
                await self.db.monthly_powers.add_voice_power_lock(
                    session,
                    monthly_power,
                    voice_xp_limit.voice_power,
                )
                await self.db.leveling_hotness.record_gain_lock(
                    session,
                    user_id,
                    voice_xp_limit.voice_power,
                )

            star_grade = await self.db.star_grades.get_star_grade_lock(
                session, user_id
            ) or await self.db.star_grades.create_star_grade_lock(session, user_id)
            grade_up_amount = 0
            prestige_amount = 0

            if voice_xp_limit.voice_shard > 0:
                star_grade, grade_ups, prestige_ups = await self.db.star_grades.add_voice_shard_lock(
                    session,
                    star_grade,
                    voice_xp_limit.voice_shard,
                )
                grade_up_amount += grade_ups
                prestige_amount += prestige_ups

            if voice_xp_limit.bonus_shard > 0:
                star_grade, grade_ups, prestige_ups = await self.db.star_grades.add_bonus_shard_lock(
                    session,
                    star_grade,
                    voice_xp_limit.bonus_shard,
                )
                grade_up_amount += grade_ups
                prestige_amount += prestige_ups

            await self.db.voice_xp_limits.delete_voice_xp_limit_lock(session, user_id)
            await session.commit()
            return VoiceXPClaimData(
                voice_xp_limit=voice_xp_limit,
                star_grade=star_grade,
                grade_up_amount=grade_up_amount,
                prestige_amount=prestige_amount,
            )
