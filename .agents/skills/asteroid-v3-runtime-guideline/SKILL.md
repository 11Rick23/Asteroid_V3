---
name: asteroid-v3-runtime-guideline
description: Use when running or changing Asteroid_V3 tooling, including uv, mise, mise.toml tasks, dependency sync, startup, local verification, Pyright, Ruff, pytest, config.yaml-dependent runs, or dev environment management.
---

# Asteroid V3 Runtime Guideline

Use this skill for local commands and tooling changes. Prefer the repo task runner when it expresses the intended workflow.

## Tools

- Use `uv` for dependency management and Python command execution.
- Use `mise` as the task runner when available.
- Keep task definitions in `mise.toml` aligned with `pyproject.toml` tooling.
- Keep `README.md` aligned when setup, startup, dependency, Docker, migration, or verification commands change.

## Common Commands

- `mise run sync`: install/sync development dependencies.
- `mise run start`: start the bot; requires `config.yaml`.
- `mise run test`: run pytest.
- `mise run format`: run Ruff formatter.
- `mise run lint`: run `uv run ruff check . --fix`; this can modify files.
- `mise run typecheck`: run Pyright.
- `mise run check`: aggregate lint, typecheck, and tests.

Use narrow commands while iterating, then broaden to `mise run check` when practical.

## Pyright/Pylance

- Prefer project-local `uv run pyright` over ad-hoc external tools.
- If import resolution is noisy, run Pyright against the project venv with `uv run pyright --pythonpath .venv/bin/python` before triaging diagnostics.
- Treat `reportAttributeAccessIssue`, `reportArgumentType`, and `reportOptionalMemberAccess` as common first-pass buckets in this Discord.py codebase.

## Startup And Config

- `mise run start` checks for `config.yaml` and then runs `uv run launch_app.py`.
- Static checks and most tests should not require a real bot token or production config.
- Do not make ordinary tests depend on live Discord or production MySQL unless the user explicitly asks for integration coverage.

## Dependencies

- Add project development tools as dev dependencies with `uv` when they are part of repeatable verification.
- Keep `uv.lock` aligned with dependency changes.
- Avoid one-off global tools when the project can own the tool version.
