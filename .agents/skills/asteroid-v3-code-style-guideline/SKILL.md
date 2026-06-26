---
name: asteroid-v3-code-style-guideline
description: Use when editing Asteroid_V3 Python style or typing, including Ruff formatting, imports, Pyright/Pylance errors, annotations, Discord.py narrowing, optional guards, overloads, casts, and code organization.
---

# Asteroid V3 Code Style Guideline

Use this skill for Python style, typing, and static-analysis work. Combine with `asteroid-v3-runtime-guideline` for exact commands.

## Baseline Style

- Use `from __future__ import annotations` in Python modules.
- Follow Ruff import ordering and formatting.
- Respect the configured 119-character line length unless readability strongly favors a split.
- Prefer clear functions and small classes over clever compression.
- Add comments only when they explain non-obvious behavior or constraints.

## Typing

- Treat Pyright/Pylance diagnostics as signals for real runtime guards, not only annotation cleanup.
- Narrow Discord.py unions explicitly. Common cases include `discord.User | discord.Member`, messageable vs non-messageable channels, nullable guild/channel/message values, and guild-only command assumptions.
- Prefer shared helpers in `app/common/discord_types.py` when a narrowing pattern repeats.
- Keep production guards strict; do not weaken runtime checks just to satisfy test fakes.
- Use `typing.cast` at clear boundaries when a framework or test double cannot express the type precisely.
- For mode-dependent repository return shapes, use `@overload` instead of broad return unions when callers need precise types.

## Discord.py Notes

- Do not assume `@app_commands.guild_only()` makes `interaction.guild` non-None to the type checker.
- Do not assume `interaction.user` is a `discord.Member`; narrow before accessing guild permissions or roles.
- Do not assume `get_channel` returns something sendable; narrow with a messageable helper.

## Organization

- Keep domain logic out of command handlers and UI callbacks when it can be tested independently.
- Prefer responsibility-focused extraction over broad utility modules.
- When a file is long, split by command group, view type, service responsibility, or domain concept.
- Existing long files are not permission to add more unrelated behavior to them.

## Verification Habit

After typing-heavy edits, run Ruff as well as Pyright. Ruff may reveal import-order or line-length regressions introduced while fixing types.
