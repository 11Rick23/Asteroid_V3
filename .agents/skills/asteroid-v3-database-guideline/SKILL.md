---
name: asteroid-v3-database-guideline
description: Use when Asteroid_V3 work touches DB-backed state, including MySQL, SQLAlchemy async models, mapped_column, repositories, dataclass DTOs, sessions, DatabaseRepositories, Alembic migrations, schema revisions, or database startup checks.
---

# Asteroid V3 Database Guideline

Use this skill when a change touches persistent state. Keep database details in the database layer and expose simple data objects to feature code.

## Stack

- Use MySQL in production-oriented configuration.
- Use SQLAlchemy async APIs.
- Use `mysql+aiomysql://...` for MySQL async connections. `mysql://...` may be normalized by `app/database/session.py`, but explicit async URLs are preferred in config examples.

## Models

- Put models in `app/database/models/`.
- Use `Mapped[...]` and `mapped_column`.
- Use MySQL dialect types where existing code does, such as unsigned `BIGINT` for Discord IDs.
- Keep table names explicit and stable.
- Add relationships only when they clearly help; existing repositories often query explicitly.

## Repositories

- Put DB operations in `app/database/repositories/`.
- Return dataclass DTOs from repositories instead of ORM models.
- Keep conversion helpers close to the repository, such as `_to_*_data`.
- Use `async with self.db.session() as session:` for session scope.
- Commit writes explicitly.
- Return `None` for missing target rows where callers can handle absence; raise only for impossible internal failures.
- Keep Discord interaction objects out of repositories.

## Wiring

When adding a repository:

1. Add the repository class under `app/database/repositories/`.
2. Export and instantiate it in `DatabaseRepositories`.
3. Add model imports where needed so metadata includes the table.
4. Add repository tests for create/update/delete/list behavior.

## Alembic And Startup

- Treat Alembic as the source of truth for schema creation and changes.
- Do not add startup-time `create_table` wiring; bot startup checks the current Alembic revision instead of creating tables.
- Keep `alembic.ini`, `app/database/migrations/env.py`, and `app/database/migrations/versions/` aligned with model changes.
- For existing databases adopting Alembic, manually stamp only the revision that matches the already-applied schema, then run `mise run db:upgrade`. For example, if the DB matches the initial baseline, use `uv run alembic stamp 273b6467e5ff`; do not stamp `head` when newer migrations add tables or columns.
- For new databases, run `uv run alembic upgrade head` before starting the bot.
- In Docker or deployment flows, run migrations explicitly before the bot process starts.

## Schema Changes

- For any model/table shape change, add or update an Alembic migration. Prefer `uv run alembic revision --autogenerate -m "..."`, then inspect and correct the generated operations.
- Verify generated migrations include every intended table, column, constraint, index, and default, and do not include unrelated churn.
- Keep migration defaults consistent with models, such as `sa.func.now()` for timestamp server defaults when models use `func.now()`.
- Include a reasonable downgrade path when practical, especially for reversible table/column additions.
- For unreleased new feature tables, prioritize the correct structure over preserving temporary local data.
- For existing features or tables that may contain real data, plan migration, compatibility, and rollback impact before changing shape.
- If changing existing data meaning, write or update a migration/helper script and tests when practical.
- Do not silently repurpose columns in a way that makes old data misleading.

## Verification

- Test pure revision checks with focused unit tests, such as `tests/test_database_migrations_check.py`.
- For repository behavior, keep create/update/delete/list tests at the repository boundary.
- When migrations or startup checks change, run the narrow relevant pytest target first, then broaden to `mise run check` when practical.
