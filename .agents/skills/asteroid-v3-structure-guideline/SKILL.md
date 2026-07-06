---
name: asteroid-v3-structure-guideline
description: Asteroid V3 project structure guide. Use when locating folders, major files, feature boundaries, app/core, app/features, app/database, app/common, tests, scripts, or change ownership.
---

# Asteroid V3 Structure Guideline

Use this skill to orient before changing code. Prefer the existing ownership boundaries over inventing new top-level layout.

## Project Map

- `app/core/`: Bot class, setup hook, config loading, logging setup, extension loading, system commands.
- `app/features/`: Discord feature implementations. Each feature entry point is normally `cog.py`.
- `app/common/`: Shared helpers for command registration, permissions, Discord.py type narrowing, constants, utilities, and pagination.
- `app/database/`: SQLAlchemy base/session/manager, models, repositories, and database compatibility wrappers.
- `tests/`: pytest tests for commands, services, repositories, config, startup, and utilities.
- `scripts/`: Operational or migration helpers such as V2 to V3 migration.
- `launch_app.py`: Bot startup entry point.
- `mise.toml`: Local task runner entry points.
- `pyproject.toml`: Python metadata, dependencies, Ruff config, dev tools.

## Feature Folder Shape

Treat `cog.py` as the feature entrance, not the place to accumulate all behavior.

Prefer these splits when a feature grows:

- `commands/`: slash command groups and command handlers.
- `views/`: View, Button, Select, Modal, persistent UI, and UI callback classes.
- `service.py` or `services/`: domain workflow and Discord operation orchestration.
- `domain/`: pure calculations, policy decisions, value objects, and small reusable logic.
- `cards/` or feature-specific subfolders: generated assets or narrow presentation helpers when already established.

Keep repositories under `app/database/repositories/` and models under `app/database/models/`; do not hide persistent storage code inside a feature folder.

## Entry Points To Check

- Feature enablement: `app/core/config.py` `FeatureFlags`.
- Extension mapping: `app/core/extensions.py` `FEATURE_EXTENSION_MAP`.
- Bot initialization and database revision checks: `app/core/bot.py`.
- Command helpers: `app/common/command_groups.py`.
- Permission helpers: `app/common/permissions.py`.
- Discord type helpers: `app/common/discord_types.py`.

Use `rg --files` and targeted `rg` searches before editing. Existing long files are not a style endorsement; when touching them, look for a scoped extraction that improves the changed area.
