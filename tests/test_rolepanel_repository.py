from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.database.models.role_panel import RolePanelCategoryModel, RolePanelRoleModel
from app.database.repositories.role_panel import RolePanel


class DummyAsyncSessionContext:
    def __init__(self, session: object) -> None:
        self.session = session

    async def __aenter__(self) -> object:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class DummyRolePanelSession:
    def __init__(
        self,
        category: RolePanelCategoryModel | None,
        roles: list[RolePanelRoleModel] | None = None,
    ) -> None:
        self.category = category
        self.roles = roles or []
        self.get_calls: list[tuple[type[object], int]] = []
        self.scalar_statements: list[object] = []

    async def get(self, model_class: type[object], category_id: int) -> RolePanelCategoryModel | None:
        self.get_calls.append((model_class, category_id))
        return self.category

    async def scalars(self, statement):
        self.scalar_statements.append(statement)
        return self.roles


def build_category_model(category_id: int) -> RolePanelCategoryModel:
    now = datetime.now()
    return RolePanelCategoryModel(
        category_id=category_id,
        name="通知",
        description=None,
        display_order=1,
        requires_boost=False,
        created_at=now,
        updated_at=now,
    )


def build_role_model(category_id: int, role_id: int, display_order: int) -> RolePanelRoleModel:
    now = datetime.now()
    return RolePanelRoleModel(
        category_id=category_id,
        role_id=role_id,
        display_order=display_order,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_get_category_fetches_target_category_and_roles_only() -> None:
    session = DummyRolePanelSession(
        build_category_model(2),
        [
            build_role_model(2, 20, 0),
            build_role_model(2, 10, 1),
        ],
    )
    repository = RolePanel(SimpleNamespace(session=lambda: DummyAsyncSessionContext(session)))

    result = await repository.get_category(2)

    assert result is not None
    assert result.category_id == 2
    assert [role.role_id for role in result.roles] == [20, 10]
    assert session.get_calls == [(RolePanelCategoryModel, 2)]
    assert len(session.scalar_statements) == 1
    statement_text = str(session.scalar_statements[0])
    assert "WHERE role_panel_roles.category_id = :category_id_1" in statement_text
    assert "ORDER BY role_panel_roles.display_order ASC, role_panel_roles.role_id ASC" in statement_text


@pytest.mark.asyncio
async def test_get_category_skips_role_query_when_category_missing() -> None:
    session = DummyRolePanelSession(None)
    repository = RolePanel(SimpleNamespace(session=lambda: DummyAsyncSessionContext(session)))

    result = await repository.get_category(999)

    assert result is None
    assert session.get_calls == [(RolePanelCategoryModel, 999)]
    assert session.scalar_statements == []
