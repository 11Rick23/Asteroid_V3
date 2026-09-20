from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.account_migration import AccountState, MigrationOptions, PendingState, merge_leveling
from app.database.leveling_state import PowerState, ShardState
from app.database.models.leveling_hotness import LevelingHotnessEventModel
from app.database.models.monthly_action_powers import MonthlyActionPowerModel
from app.database.models.monthly_powers import MonthlyPowerModel
from app.database.models.star_grades import StarGradeModel
from app.database.models.user_birthdays import UserBirthdayModel
from app.database.models.user_roles import UserRoleModel
from app.database.models.voice_xp_limits import VoiceXPLimitModel


class AccountMigrationRepository:
    def __init__(self, db: Any) -> None:
        self.db = db

    async def read(self, session: AsyncSession, user_id: int, *, lock: bool = False) -> AccountState:
        shard = await session.get(StarGradeModel, user_id, with_for_update=lock)
        power = await session.get(MonthlyPowerModel, user_id, with_for_update=lock)
        action = await session.get(MonthlyActionPowerModel, user_id, with_for_update=lock)
        pending = await session.get(VoiceXPLimitModel, user_id, with_for_update=lock)
        birthday = await session.get(UserBirthdayModel, user_id, with_for_update=lock)
        stmt = select(UserRoleModel.role_id).where(UserRoleModel.user_id == user_id)
        if lock:
            stmt = stmt.with_for_update()
        roles = await session.scalars(stmt)
        return AccountState(
            user_id,
            ShardState(shard.text_shard, shard.voice_shard, shard.bonus_shard) if shard else ShardState(),
            PowerState(
                power.text_power if power else 0,
                power.voice_power if power else 0,
                action.action_power if action else 0,
            ),
            PendingState(
                pending.voice_shard, pending.bonus_shard, pending.voice_power, pending.half_notify, pending.full_notify
            )
            if pending
            else PendingState(),
            birthday.date if birthday else None,
            tuple(sorted(roles)),
        )

    async def read_pair(self, source_id: int, target_id: int) -> tuple[AccountState, AccountState]:
        async with self.db.leveling.user_updates(source_id, target_id):
            async with self.db.session() as session:
                return await self.read(session, source_id), await self.read(session, target_id)

    async def write_pending(self, session: AsyncSession, user_id: int, values: PendingState) -> None:
        values.validate()
        model = await session.get(VoiceXPLimitModel, user_id)
        if model is None:
            model = VoiceXPLimitModel(user_id=user_id)
            session.add(model)
        model.voice_shard, model.bonus_shard, model.voice_power = (
            values.voice_shard,
            values.bonus_shard,
            values.voice_power,
        )
        model.half_notify, model.full_notify = values.half_notify, values.full_notify

    async def set_pending(self, user_id: int, values: PendingState) -> None:
        async with self.db.leveling.user_updates(user_id):
            async with self.db.session() as session:
                await self.write_pending(session, user_id, values)
                await session.commit()

    async def apply(
        self,
        session: AsyncSession,
        source: AccountState,
        target: AccountState,
        options: MigrationOptions,
        target_roles: tuple[int, ...],
        remaining_roles: tuple[int, ...],
    ) -> None:
        if options.leveling:
            shards, powers, pending = merge_leveling(source, target)
            await self.db.leveling_state.write_shards(session, target.user_id, shards)
            await self.db.leveling_state.write_powers(session, target.user_id, powers)
            await self.write_pending(session, target.user_id, pending)
            await self.db.leveling_state.write_shards(session, source.user_id, ShardState())
            await self.db.leveling_state.write_powers(session, source.user_id, PowerState())
            await self.write_pending(session, source.user_id, PendingState())
            await session.execute(
                update(LevelingHotnessEventModel)
                .where(LevelingHotnessEventModel.user_id == source.user_id)
                .values(user_id=target.user_id)
            )
        if options.birthday:
            await session.execute(
                delete(UserBirthdayModel).where(UserBirthdayModel.user_id.in_([source.user_id, target.user_id]))
            )
            if source.birthday is not None:
                session.add(UserBirthdayModel(user_id=target.user_id, date=source.birthday))
        if options.roles:
            await session.execute(
                delete(UserRoleModel).where(UserRoleModel.user_id.in_([source.user_id, target.user_id]))
            )
            session.add_all([UserRoleModel(user_id=target.user_id, role_id=role_id) for role_id in target_roles])
            session.add_all([UserRoleModel(user_id=source.user_id, role_id=role_id) for role_id in remaining_roles])
        await session.flush()
