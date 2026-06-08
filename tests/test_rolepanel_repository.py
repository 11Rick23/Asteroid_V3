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
        if hasattr(self.session, "closed"):
            self.session.closed = True
        return False


class DummyScalarResult:
    def __init__(self, session: object, rows: list[object]) -> None:
        self.session = session
        self.rows = rows
        self.all_called = False

    def all(self) -> list[object]:
        if getattr(self.session, "closed", False):
            raise AssertionError("ScalarResult was consumed after the session was closed")
        self.all_called = True
        return self.rows

    def __iter__(self):
        if getattr(self.session, "closed", False):
            raise AssertionError("ScalarResult was iterated after the session was closed")
        return iter(self.rows)


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
        self.scalar_results: list[DummyScalarResult] = []
        self.closed = False

    async def get(self, model_class: type[object], category_id: int) -> RolePanelCategoryModel | None:
        self.get_calls.append((model_class, category_id))
        return self.category

    async def scalars(self, statement):
        self.scalar_statements.append(statement)
        result = DummyScalarResult(self, self.roles)
        self.scalar_results.append(result)
        return result


class DummyRolePanelListSession:
    def __init__(
        self,
        categories: list[RolePanelCategoryModel],
        roles: list[RolePanelRoleModel],
    ) -> None:
        self.scalar_rows: list[list[object]] = [categories, roles]
        self.scalar_statements: list[object] = []
        self.scalar_results: list[DummyScalarResult] = []
        self.closed = False

    async def scalars(self, statement):
        self.scalar_statements.append(statement)
        result = DummyScalarResult(self, self.scalar_rows.pop(0))
        self.scalar_results.append(result)
        return result


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
    assert session.scalar_results[0].all_called is True
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


@pytest.mark.asyncio
async def test_get_categories_materializes_results_before_session_closes() -> None:
    session = DummyRolePanelListSession(
        [build_category_model(1), build_category_model(2)],
        [
            build_role_model(1, 10, 0),
            build_role_model(2, 20, 0),
        ],
    )
    repository = RolePanel(SimpleNamespace(session=lambda: DummyAsyncSessionContext(session)))

    result = await repository.get_categories()

    assert [category.category_id for category in result] == [1, 2]
    assert [[role.role_id for role in category.roles] for category in result] == [[10], [20]]
    assert len(session.scalar_statements) == 2
    assert [scalar_result.all_called for scalar_result in session.scalar_results] == [True, True]
