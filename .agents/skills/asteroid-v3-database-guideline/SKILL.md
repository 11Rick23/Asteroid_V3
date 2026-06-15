---
name: asteroid-v3-database-guideline
description: Use when Asteroid_V3 work touches DB-backed state, including MySQL, SQLAlchemy async models, mapped_column, repositories, dataclass DTOs, sessions, DatabaseRepositories, table initialization, or migrations.
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
4. Add table initialization/drop behavior where the existing initialization flow requires it.
5. Add repository tests for create/update/delete/list behavior.

## Schema Changes

- For unreleased new feature tables, prioritize the correct structure over preserving temporary local data.
- For existing features or tables that may contain real data, plan migration, compatibility, and rollback impact before changing shape.
- If changing existing data meaning, write or update a migration/helper script and tests when practical.
- Do not silently repurpose columns in a way that makes old data misleading.
