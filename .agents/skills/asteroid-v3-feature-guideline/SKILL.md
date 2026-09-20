---
name: asteroid-v3-feature-guideline
description: Use when adding, modifying, or refactoring Asteroid_V3 features, extensions, cogs, event listeners, scheduled tasks, services, views, command modules, user-facing messages, guild-scoped behavior, feature config, flags, or feature folders.
---

# Asteroid V3 Feature Guideline

Use with `asteroid-v3-app-command-guideline` for commands/UI, `asteroid-v3-database-guideline` for persistence, and `asteroid-v3-logging-guideline` for logs.

## Feature Wiring

When adding a feature:

1. Put deploy/server settings in `app/core/config.py`.
2. Add a `FeatureFlags` boolean for enable/disable behavior.
3. Add the extension to alphabetized `FEATURE_EXTENSION_MAP` in `app/core/extensions.py`.
4. Add `async setup(bot: AsteroidBot) -> None` in the extension.
5. Update `README.md` when the feature list, setup notes, or user-facing capability summary changes.
6. Test flag loading, extension selection, command registration, and core behavior.

Keep `config.example.yaml` and `README.md` aligned when new user-facing config is required.

## Operating Guild Scope

- Run guild events and feature side effects only when `bot.is_operating_guild(...)` or `bot.is_operating_guild_id(...)` accepts the source.
- Ignore DMs and events from guilds other than `config.discord.guild_id`; guard at the listener before cache, DB, service, or Discord mutations.
- Restrict loops over `bot.guilds`, raw events, and configured destination channels to the operating guild.
- Validate configured channels with `bot.is_operating_channel(...)` before sending, editing, or deleting messages.
- Use `asteroid-v3-app-command-guideline` for command, View, and Modal scope checks.

## Responsibility Split

- Cog: register commands/views, receive events, connect dependencies, handle immediate responses.
- Commands: command groups and handlers once they outgrow a small set.
- Views: Discord UI classes and callback authorization.
- Service: workflows, domain decisions, embed helpers, Discord operation planning.
- Domain: pure logic, calculations, policy, testable values.
- Messages: feature-owned user-facing copy and its formatting, without Discord operations or domain decisions.
- Repository: DB reads/writes in `app/database/repositories/`, not Cog/View/Service.

## User-Facing Messages

- Put feature-owned user-facing copy in `app/features/<feature>/messages.py` by default.
- Use module constants for fixed copy and typed functions with explicit arguments for copy that contains runtime values.
- Pass primitive or already-formatted display values into message functions; keep Discord lookups, permission decisions, DB access, and side effects in the caller.
- A narrow immutable value object is acceptable when one response always carries multiple related values such as a title and description.
- Do not move logger text, audit identifiers, `custom_id` values, command names, database values, or operational reasons into the message catalog only to eliminate literals.
- Preserve existing wording, whitespace, Markdown, mentions, emoji, and visibility unless the task explicitly changes the user-facing contract.
- When a message catalog approaches 300 lines or mixes several independent areas, replace `messages.py` with a `messages/` package and split by responsibility, such as `commands.py`, `views.py`, or `ranking.py`.
- Keep `messages/__init__.py` small. Re-export only stable names needed by callers; do not rebuild the entire catalog in the package entry point.
- Do not keep sibling `messages.py` and `messages/` paths at the same time.

## File Size And Splitting

Split assertively:

- Start extraction around 300 lines.
- Discord UI, View, Modal, Select, Button, and command groups are not exceptions.
- `cog.py` may be longer only as entrance/dependency connector; never as a catch-all.
- Move growing commands into `commands/`; growing UI into `views/` or purpose-specific modules.
- Move a growing `messages.py` into a responsibility-focused `messages/` package instead of treating message catalogs as a size exception.
- Extract domain logic, permission decisions, display data, embed builders, and DB coordination out of callbacks when practical.
- Existing long files may remain until touched; new/nearby work should move toward focused files.

## Config Style

- Use Pydantic models in `app/core/config.py`; keep `extra="forbid"`.
- Use `0` for unset Discord IDs and `Field(default_factory=list)` for list defaults.
- Config is for deploy/server IDs, toggles, limits, cooldowns, and behavior that should vary without code edits.
- Do not configure truly internal constants.
