from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

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


@dataclass(slots=True)
class LevelingShardUpdateData:
    star_grade: StarGradeData
    grade_up_amount: int
    prestige_amount: int


class LevelingTransactions:
    def __init__(self, db):
        self.db = db
        self._condition = asyncio.Condition()
        self._monthly_power_reset_requested = False
        self._resetting_monthly_power = False
        self._active_user_updates = 0
        self._user_locks: dict[int, asyncio.Lock] = {}

    @asynccontextmanager
    async def _user_update(self, user_id: int) -> AsyncIterator[None]:
        async with self._condition:
            while self._monthly_power_reset_requested or self._resetting_monthly_power:
                await self._condition.wait()
            self._active_user_updates += 1

        lock = self._user_locks.setdefault(user_id, asyncio.Lock())
        try:
            async with lock:
                yield
        finally:
            async with self._condition:
                self._active_user_updates -= 1
                if self._active_user_updates == 0:
                    self._condition.notify_all()

    @asynccontextmanager
    async def _monthly_power_reset(self) -> AsyncIterator[None]:
        async with self._condition:
            while self._monthly_power_reset_requested or self._resetting_monthly_power:
                await self._condition.wait()
            self._monthly_power_reset_requested = True
            while self._active_user_updates > 0:
                await self._condition.wait()
            self._resetting_monthly_power = True

        try:
            yield
        finally:
            async with self._condition:
                self._resetting_monthly_power = False
                self._monthly_power_reset_requested = False
                self._condition.notify_all()

    async def add_action_power(self, user_id: int, amount: int) -> MonthlyActionPowerData:
        async with self._user_update(user_id):
            return await self._add_action_power(user_id, amount)

    async def _add_action_power(self, user_id: int, amount: int) -> MonthlyActionPowerData:
        async with self.db.session() as session:
            action_power = await self.db.monthly_action_powers.get_monthly_action_power_in_session(
                session, user_id
            ) or await self.db.monthly_action_powers.create_monthly_action_power_in_session(session, user_id)
            updated = await self.db.monthly_action_powers.add_action_power_in_session(session, action_power, amount)
            if amount > 0:
                await self.db.leveling_hotness.record_gain_in_session(session, user_id, amount)
            await session.commit()
            return updated

    async def add_text_power(self, user_id: int, amount: int) -> MonthlyPowerData:
        async with self._user_update(user_id):
            async with self.db.session() as session:
                updated = await self._add_monthly_power_in_session(session, user_id, "text", amount)
                await session.commit()
                return updated

    async def add_voice_power(self, user_id: int, amount: int) -> MonthlyPowerData:
        async with self._user_update(user_id):
            async with self.db.session() as session:
                updated = await self._add_monthly_power_in_session(session, user_id, "voice", amount)
                await session.commit()
                return updated

    async def remove_action_power(self, user_id: int, amount: int) -> MonthlyActionPowerData:
        async with self._user_update(user_id):
            return await self._remove_action_power(user_id, amount)

    async def _remove_action_power(self, user_id: int, amount: int) -> MonthlyActionPowerData:
        async with self.db.session() as session:
            action_power = await self.db.monthly_action_powers.get_monthly_action_power_in_session(
                session, user_id
            ) or await self.db.monthly_action_powers.create_monthly_action_power_in_session(session, user_id)
            updated = await self.db.monthly_action_powers.remove_action_power_in_session(session, action_power, amount)
            await session.commit()
            return updated

    async def apply_message_reward(
        self,
        user_id: int,
        power_amount: int,
        bonus_shard_amount: int,
    ) -> LevelingRewardData:
        async with self._user_update(user_id):
            return await self._apply_message_reward(user_id, power_amount, bonus_shard_amount)

    async def _apply_message_reward(
        self,
        user_id: int,
        power_amount: int,
        bonus_shard_amount: int,
    ) -> LevelingRewardData:
        async with self.db.session() as session:
            monthly_power = await self.db.monthly_powers.get_monthly_power_in_session(
                session, user_id
            ) or await self.db.monthly_powers.create_monthly_power_in_session(session, user_id)
            await self.db.monthly_powers.add_text_power_in_session(session, monthly_power, power_amount)
            if power_amount > 0:
                await self.db.leveling_hotness.record_gain_in_session(
                    session,
                    user_id,
                    power_amount,
                )

            star_grade = await self.db.star_grades.get_star_grade_in_session(
                session, user_id
            ) or await self.db.star_grades.create_star_grade_in_session(session, user_id)
            star_grade, text_grade_ups, text_prestige_ups = await self.db.star_grades.add_text_shard_in_session(
                session, star_grade, power_amount
            )

            bonus_grade_ups = 0
            bonus_prestige_ups = 0
            if bonus_shard_amount > 0:
                (
                    star_grade,
                    bonus_grade_ups,
                    bonus_prestige_ups,
                ) = await self.db.star_grades.add_bonus_shard_in_session(
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
        async with self._user_update(user_id):
            return await self._accrue_voice_xp(
                user_id,
                voice_power_amount=voice_power_amount,
                voice_shard_amount=voice_shard_amount,
                bonus_shard_amount=bonus_shard_amount,
                limit=limit,
            )

    async def _accrue_voice_xp(
        self,
        user_id: int,
        *,
        voice_power_amount: int,
        voice_shard_amount: int,
        bonus_shard_amount: int,
        limit: int,
    ) -> VoiceXPAccrualData:
        async with self.db.session() as session:
            data = await self.db.voice_xp_limits.get_voice_xp_limit_in_session(
                session, user_id
            ) or await self.db.voice_xp_limits.create_voice_xp_limit_in_session(session, user_id)
            was_half_notified = data.half_notify
            was_full_notified = data.full_notify

            if data.voice_power < limit:
                data, _, _ = await self.db.voice_xp_limits.add_voice_power_in_session(
                    session,
                    data,
                    voice_power_amount,
                    limit,
                )

            if (data.voice_shard + data.bonus_shard) < limit:
                data, _, limit_reached = await self.db.voice_xp_limits.add_voice_shard_in_session(
                    session,
                    data,
                    voice_shard_amount,
                    limit,
                )
                if bonus_shard_amount > 0 and not limit_reached:
                    data, _, _ = await self.db.voice_xp_limits.add_bonus_shard_in_session(
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
        async with self._user_update(user_id):
            return await self._claim_voice_xp(user_id)

    async def _claim_voice_xp(self, user_id: int) -> VoiceXPClaimData | None:
        async with self.db.session() as session:
            voice_xp_limit = await self.db.voice_xp_limits.get_voice_xp_limit_in_session(session, user_id)
            if (
                voice_xp_limit is None
                or (voice_xp_limit.voice_shard + voice_xp_limit.bonus_shard + voice_xp_limit.voice_power) < 1
            ):
                return None

            monthly_power = await self.db.monthly_powers.get_monthly_power_in_session(
                session, user_id
            ) or await self.db.monthly_powers.create_monthly_power_in_session(session, user_id)
            if voice_xp_limit.voice_power > 0:
                await self.db.monthly_powers.add_voice_power_in_session(
                    session,
                    monthly_power,
                    voice_xp_limit.voice_power,
                )
                await self.db.leveling_hotness.record_gain_in_session(
                    session,
                    user_id,
                    voice_xp_limit.voice_power,
                )

            star_grade = await self.db.star_grades.get_star_grade_in_session(
                session, user_id
            ) or await self.db.star_grades.create_star_grade_in_session(session, user_id)
            grade_up_amount = 0
            prestige_amount = 0

            if voice_xp_limit.voice_shard > 0:
                star_grade, grade_ups, prestige_ups = await self.db.star_grades.add_voice_shard_in_session(
                    session,
                    star_grade,
                    voice_xp_limit.voice_shard,
                )
                grade_up_amount += grade_ups
                prestige_amount += prestige_ups

            if voice_xp_limit.bonus_shard > 0:
                star_grade, grade_ups, prestige_ups = await self.db.star_grades.add_bonus_shard_in_session(
                    session,
                    star_grade,
                    voice_xp_limit.bonus_shard,
                )
                grade_up_amount += grade_ups
                prestige_amount += prestige_ups

            await self.db.voice_xp_limits.delete_voice_xp_limit_in_session(session, user_id)
            await session.commit()
            return VoiceXPClaimData(
                voice_xp_limit=voice_xp_limit,
                star_grade=star_grade,
                grade_up_amount=grade_up_amount,
                prestige_amount=prestige_amount,
            )

    async def add_shard(self, user_id: int, shard_type: str, amount: int) -> LevelingShardUpdateData:
        async with self._user_update(user_id):
            async with self.db.session() as session:
                star_grade = await self.db.star_grades.get_star_grade_in_session(
                    session, user_id
                ) or await self.db.star_grades.create_star_grade_in_session(session, user_id)
                if shard_type == "テキスト":
                    star_grade, grade_up_amount, prestige_amount = await self.db.star_grades.add_text_shard_in_session(
                        session, star_grade, amount
                    )
                elif shard_type == "ボイス":
                    star_grade, grade_up_amount, prestige_amount = (
                        await self.db.star_grades.add_voice_shard_in_session(session, star_grade, amount)
                    )
                else:
                    star_grade, grade_up_amount, prestige_amount = (
                        await self.db.star_grades.add_bonus_shard_in_session(session, star_grade, amount)
                    )
                await session.commit()
            return LevelingShardUpdateData(star_grade, grade_up_amount, prestige_amount)

    async def remove_shard(self, user_id: int, shard_type: str, amount: int) -> LevelingShardUpdateData:
        async with self._user_update(user_id):
            async with self.db.session() as session:
                star_grade = await self.db.star_grades.get_star_grade_in_session(
                    session, user_id
                ) or await self.db.star_grades.create_star_grade_in_session(session, user_id)
                if shard_type == "テキスト":
                    star_grade, grade_up_amount, prestige_amount = (
                        await self.db.star_grades.remove_text_shard_in_session(session, star_grade, amount)
                    )
                elif shard_type == "ボイス":
                    star_grade, grade_up_amount, prestige_amount = (
                        await self.db.star_grades.remove_voice_shard_in_session(session, star_grade, amount)
                    )
                else:
                    star_grade, grade_up_amount, prestige_amount = (
                        await self.db.star_grades.remove_bonus_shard_in_session(session, star_grade, amount)
                    )
                await session.commit()
            return LevelingShardUpdateData(star_grade, grade_up_amount, prestige_amount)

    async def add_power(self, user_id: int, power_type: str, amount: int) -> MonthlyPowerData:
        async with self._user_update(user_id):
            async with self.db.session() as session:
                if power_type == "action":
                    updated = await self._add_action_power_and_get_monthly_power_in_session(session, user_id, amount)
                else:
                    updated = await self._add_monthly_power_in_session(session, user_id, power_type, amount)
                await session.commit()
                return updated

    async def remove_power(self, user_id: int, power_type: str, amount: int) -> MonthlyPowerData:
        async with self._user_update(user_id):
            async with self.db.session() as session:
                if power_type == "action":
                    updated = await self._remove_action_power_and_get_monthly_power_in_session(
                        session, user_id, amount
                    )
                else:
                    updated = await self._remove_monthly_power_in_session(session, user_id, power_type, amount)
                await session.commit()
                return updated

    async def apply_mee6_transfer(
        self,
        user_id: int,
        *,
        text_shard: int,
        text_prestige: int,
    ) -> LevelingShardUpdateData:
        async with self._user_update(user_id):
            async with self.db.session() as session:
                star_grade = await self.db.star_grades.get_star_grade_in_session(
                    session, user_id
                ) or await self.db.star_grades.create_star_grade_in_session(session, user_id)
                if text_prestige > 0:
                    star_grade, _, _, _ = await self.db.star_grades.add_prestige_in_session(
                        session, star_grade, text_prestige, "テキスト"
                    )

                star_grade, grade_up_amount, prestige_amount = await self.db.star_grades.add_text_shard_in_session(
                    session, star_grade, text_shard
                )
                await session.commit()
            return LevelingShardUpdateData(star_grade, grade_up_amount, prestige_amount)

    async def reset_monthly_power_state(self) -> None:
        async with self._monthly_power_reset():
            await self.db.monthly_powers.reset_monthly_powers()
            await self.db.monthly_action_powers.reset_monthly_action_powers()
            await self.db.voice_xp_limits.reset_voice_power()

    async def _add_monthly_power_in_session(
        self,
        session: AsyncSession,
        user_id: int,
        power_type: str,
        amount: int,
    ) -> MonthlyPowerData:
        monthly_power = await self.db.monthly_powers.get_monthly_power_in_session(
            session, user_id
        ) or await self.db.monthly_powers.create_monthly_power_in_session(session, user_id)
        if power_type == "text":
            updated = await self.db.monthly_powers.add_text_power_in_session(session, monthly_power, amount)
        else:
            updated = await self.db.monthly_powers.add_voice_power_in_session(session, monthly_power, amount)
        if amount > 0:
            await self.db.leveling_hotness.record_gain_in_session(session, user_id, amount)
        return updated

    async def _remove_monthly_power_in_session(
        self,
        session: AsyncSession,
        user_id: int,
        power_type: str,
        amount: int,
    ) -> MonthlyPowerData:
        monthly_power = await self.db.monthly_powers.get_monthly_power_in_session(
            session, user_id
        ) or await self.db.monthly_powers.create_monthly_power_in_session(session, user_id)
        if power_type == "text":
            return await self.db.monthly_powers.remove_text_power_in_session(session, monthly_power, amount)
        return await self.db.monthly_powers.remove_voice_power_in_session(session, monthly_power, amount)

    async def _add_action_power_and_get_monthly_power_in_session(
        self,
        session: AsyncSession,
        user_id: int,
        amount: int,
    ) -> MonthlyPowerData:
        monthly_power = await self.db.monthly_powers.get_monthly_power_in_session(
            session, user_id
        ) or await self.db.monthly_powers.create_monthly_power_in_session(session, user_id)
        action_power = await self.db.monthly_action_powers.get_monthly_action_power_in_session(
            session, user_id
        ) or await self.db.monthly_action_powers.create_monthly_action_power_in_session(session, user_id)
        action_power = await self.db.monthly_action_powers.add_action_power_in_session(session, action_power, amount)
        if amount > 0:
            await self.db.leveling_hotness.record_gain_in_session(session, user_id, amount)
        return MonthlyPowerData(
            monthly_power.user_id,
            monthly_power.text_power,
            monthly_power.voice_power,
            action_power.action_power,
            monthly_power.created_at,
            monthly_power.updated_at,
        )

    async def _remove_action_power_and_get_monthly_power_in_session(
        self,
        session: AsyncSession,
        user_id: int,
        amount: int,
    ) -> MonthlyPowerData:
        monthly_power = await self.db.monthly_powers.get_monthly_power_in_session(
            session, user_id
        ) or await self.db.monthly_powers.create_monthly_power_in_session(session, user_id)
        action_power = await self.db.monthly_action_powers.get_monthly_action_power_in_session(
            session, user_id
        ) or await self.db.monthly_action_powers.create_monthly_action_power_in_session(session, user_id)
        action_power = await self.db.monthly_action_powers.remove_action_power_in_session(
            session, action_power, amount
        )
        return MonthlyPowerData(
            monthly_power.user_id,
            monthly_power.text_power,
            monthly_power.voice_power,
            action_power.action_power,
            monthly_power.created_at,
            monthly_power.updated_at,
        )
