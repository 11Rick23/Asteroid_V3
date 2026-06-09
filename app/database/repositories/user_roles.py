from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import discord
from sqlalchemy import delete, select

from app.common.utils import generate_timestamp
from app.database.models.user_roles import UserRoleModel
from app.database.table_utils import model_table


@dataclass
class UserRoleData:
    user_id: int
    role_id: int
    created_at: datetime
    updated_at: datetime


class UserRoles:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _to_data(model: UserRoleModel | None) -> UserRoleData | None:
        if model is None:
            return None
        return UserRoleData(
            user_id=model.user_id,
            role_id=model.role_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def create_table(self) -> None:
        async with self.db.engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: model_table(UserRoleModel).create(sync_conn, checkfirst=True))

    async def drop_table(self) -> None:
        async with self.db.engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: model_table(UserRoleModel).drop(sync_conn, checkfirst=True))

    async def get_user_roles(self, user_id: int) -> list[UserRoleData]:
        async with self.db.session() as session:
            stmt = select(UserRoleModel).where(UserRoleModel.user_id == user_id)
            raw_roles = await session.scalars(stmt)
            return [role for raw_role in raw_roles if (role := self._to_data(raw_role)) is not None]

    async def save_user_roles(self, member: discord.Member) -> None:
        ignored_save_role_ids = self.db.config.roles.ignored_save_role_id_list
        models: list[UserRoleModel] = []
        for role in member.roles:
            if (
                role == member.guild.default_role
                or role >= member.guild.me.top_role
                or role.id in ignored_save_role_ids
            ):
                continue
            models.append(UserRoleModel(user_id=member.id, role_id=role.id))

        async with self.db.session() as session:
            await session.execute(delete(UserRoleModel).where(UserRoleModel.user_id == member.id))
            if models:
                session.add_all(models)
            await session.commit()

    async def delete_user_roles(self, user_id: int) -> None:
        async with self.db.session() as session:
            await session.execute(delete(UserRoleModel).where(UserRoleModel.user_id == user_id))
            await session.commit()

    async def delete_user_role(self, user_id: int, role_id: int) -> None:
        async with self.db.session() as session:
            model = await session.get(UserRoleModel, (user_id, role_id))
            if model is not None:
                await session.delete(model)
                await session.commit()

    async def restore_user_roles(self, member: discord.Member) -> int:
        roles_data = await self.get_user_roles(member.id)
        append_roles: list[discord.Role] = []
        for role_data in roles_data:
            role = member.guild.get_role(role_data.role_id)
            if role is None:
                await self.delete_user_role(member.id, role_data.role_id)
                continue
            if role < member.guild.me.top_role:
                append_roles.append(role)
        if append_roles:
            await member.add_roles(
                *append_roles,
                reason=f"[{generate_timestamp()}] ロール復元機能により付与されました。",
                atomic=False,
            )
        return len(append_roles)
