---
name: asteroid-v3-feature-guideline
description: Use when adding, modifying, or refactoring Asteroid_V3 features, extensions, cogs, event listeners, scheduled tasks, services, views, command modules, guild-scoped behavior, feature config, flags, or feature folders.
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
- Repository: DB reads/writes in `app/database/repositories/`, not Cog/View/Service.

## File Size And Splitting

Split assertively:

- Start extraction around 300 lines.
- Discord UI, View, Modal, Select, Button, and command groups are not exceptions.
- `cog.py` may be longer only as entrance/dependency connector; never as a catch-all.
- Move growing commands into `commands/`; growing UI into `views/` or purpose-specific modules.
- Extract domain logic, permission decisions, display data, embed builders, and DB coordination out of callbacks when practical.
- Existing long files may remain until touched; new/nearby work should move toward focused files.

## Config Style

- Use Pydantic models in `app/core/config.py`; keep `extra="forbid"`.
- Use `0` for unset Discord IDs and `Field(default_factory=list)` for list defaults.
- Config is for deploy/server IDs, toggles, limits, cooldowns, and behavior that should vary without code edits.
- Do not configure truly internal constants.
