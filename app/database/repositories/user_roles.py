from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select

from app.database.models.user_roles import UserRoleModel


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

    async def get_user_roles(self, user_id: int) -> list[UserRoleData]:
        async with self.db.session() as session:
            stmt = select(UserRoleModel).where(UserRoleModel.user_id == user_id)
            raw_roles = await session.scalars(stmt)
            return [role for raw_role in raw_roles if (role := self._to_data(raw_role)) is not None]

    async def save_user_roles(self, user_id: int, role_ids: list[int]) -> None:
        async with self.db.session() as session:
            await session.execute(delete(UserRoleModel).where(UserRoleModel.user_id == user_id))
            models = [UserRoleModel(user_id=user_id, role_id=role_id) for role_id in role_ids]
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
