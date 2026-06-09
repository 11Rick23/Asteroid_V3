from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import delete, select

from app.database.models.role_panel import (
    RolePanelCategoryModel,
    RolePanelRoleModel,
)
from app.database.table_utils import model_table


@dataclass
class RolePanelCategoryData:
    category_id: int
    name: str
    description: str | None
    display_order: int
    requires_boost: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class RolePanelRoleData:
    category_id: int
    role_id: int
    display_order: int
    created_at: datetime
    updated_at: datetime


@dataclass
class RolePanelCategoryDetail(RolePanelCategoryData):
    roles: list[RolePanelRoleData] = field(default_factory=list)


class RolePanel:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _to_category_data(model: RolePanelCategoryModel | None) -> RolePanelCategoryData | None:
        if model is None:
            return None
        return RolePanelCategoryData(
            category_id=model.category_id,
            name=model.name,
            description=model.description,
            display_order=model.display_order,
            requires_boost=model.requires_boost,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_role_data(model: RolePanelRoleModel | None) -> RolePanelRoleData | None:
        if model is None:
            return None
        return RolePanelRoleData(
            category_id=model.category_id,
            role_id=model.role_id,
            display_order=model.display_order,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def create_table(self) -> None:
        async with self.db.engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: model_table(RolePanelCategoryModel).create(sync_conn, checkfirst=True)
            )
            await conn.run_sync(lambda sync_conn: model_table(RolePanelRoleModel).create(sync_conn, checkfirst=True))

    async def drop_table(self) -> None:
        async with self.db.engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: model_table(RolePanelRoleModel).drop(sync_conn, checkfirst=True))
            await conn.run_sync(lambda sync_conn: model_table(RolePanelCategoryModel).drop(sync_conn, checkfirst=True))

    async def create_category(
        self,
        name: str,
        description: str | None = None,
        display_order: int = 0,
        requires_boost: bool = False,
    ) -> RolePanelCategoryData:
        async with self.db.session() as session:
            now = datetime.now()
            model = RolePanelCategoryModel(
                name=name,
                description=description,
                display_order=display_order,
                requires_boost=requires_boost,
                created_at=now,
                updated_at=now,
            )
            session.add(model)
            await session.flush()
            data = self._to_category_data(model)
            await session.commit()
        if data is None:
            raise RuntimeError("ロールパネルカテゴリの作成に失敗しました。")
        return data

    async def update_category(
        self,
        category_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        display_order: int | None = None,
        requires_boost: bool | None = None,
    ) -> RolePanelCategoryData | None:
        async with self.db.session() as session:
            model = await session.get(RolePanelCategoryModel, category_id)
            if model is None:
                return None
            if name is not None:
                model.name = name
            if description is not None:
                model.description = description
            if display_order is not None:
                model.display_order = display_order
            if requires_boost is not None:
                model.requires_boost = requires_boost
            now = datetime.now()
            model.updated_at = now
            data = self._to_category_data(model)
            await session.commit()
            return data

    async def delete_category(self, category_id: int) -> bool:
        async with self.db.session() as session:
            result = await session.execute(
                delete(RolePanelCategoryModel).where(RolePanelCategoryModel.category_id == category_id)
            )
            await session.commit()
            return bool(result.rowcount)

    async def get_category(self, category_id: int) -> RolePanelCategoryDetail | None:
        async with self.db.session() as session:
            category_model = await session.get(RolePanelCategoryModel, category_id)
            category_data = self._to_category_data(category_model)
            if category_data is None:
                return None

            role_stmt = (
                select(RolePanelRoleModel)
                .where(RolePanelRoleModel.category_id == category_id)
                .order_by(
                    RolePanelRoleModel.display_order.asc(),
                    RolePanelRoleModel.role_id.asc(),
                )
            )
            role_models = (await session.scalars(role_stmt)).all()

        category = RolePanelCategoryDetail(**category_data.__dict__)
        category.roles = [
            role_data for model in role_models if (role_data := self._to_role_data(model)) is not None
        ]
        return category

    async def get_categories(self) -> list[RolePanelCategoryDetail]:
        async with self.db.session() as session:
            category_stmt = select(RolePanelCategoryModel).order_by(
                RolePanelCategoryModel.display_order.asc(),
                RolePanelCategoryModel.category_id.asc(),
            )
            role_stmt = select(RolePanelRoleModel).order_by(
                RolePanelRoleModel.category_id.asc(),
                RolePanelRoleModel.display_order.asc(),
                RolePanelRoleModel.role_id.asc(),
            )
            category_models = (await session.scalars(category_stmt)).all()
            role_models = (await session.scalars(role_stmt)).all()

        categories: list[RolePanelCategoryDetail] = []
        category_by_id: dict[int, RolePanelCategoryDetail] = {}
        for model in category_models:
            category_data = self._to_category_data(model)
            if category_data is None:
                continue
            category = RolePanelCategoryDetail(**category_data.__dict__)
            categories.append(category)
            category_by_id[category.category_id] = category

        for model in role_models:
            role_data = self._to_role_data(model)
            if role_data is not None and role_data.category_id in category_by_id:
                category_by_id[role_data.category_id].roles.append(role_data)

        return categories

    async def add_role(self, category_id: int, role_id: int, display_order: int = 0) -> RolePanelRoleData | None:
        async with self.db.session() as session:
            if await session.get(RolePanelCategoryModel, category_id) is None:
                return None
            model = await session.get(RolePanelRoleModel, (category_id, role_id))
            if model is None:
                now = datetime.now()
                model = RolePanelRoleModel(
                    category_id=category_id,
                    role_id=role_id,
                    display_order=display_order,
                    created_at=now,
                    updated_at=now,
                )
                session.add(model)
                await session.flush()
            else:
                model.display_order = display_order
            data = self._to_role_data(model)
            await session.commit()
            return data

    async def remove_role(self, category_id: int, role_id: int) -> bool:
        async with self.db.session() as session:
            result = await session.execute(
                delete(RolePanelRoleModel).where(
                    RolePanelRoleModel.category_id == category_id,
                    RolePanelRoleModel.role_id == role_id,
                )
            )
            await session.commit()
            return bool(result.rowcount)

    async def set_roles(self, category_id: int, role_ids: list[int]) -> list[RolePanelRoleData] | None:
        async with self.db.session() as session:
            if await session.get(RolePanelCategoryModel, category_id) is None:
                return None
            await session.execute(delete(RolePanelRoleModel).where(RolePanelRoleModel.category_id == category_id))
            now = datetime.now()
            models = [
                RolePanelRoleModel(
                    category_id=category_id,
                    role_id=role_id,
                    display_order=index,
                    created_at=now,
                    updated_at=now,
                )
                for index, role_id in enumerate(role_ids)
            ]
            if models:
                session.add_all(models)
                await session.flush()
            data = [role_data for model in models if (role_data := self._to_role_data(model)) is not None]
            await session.commit()
            return data
