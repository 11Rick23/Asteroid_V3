---
name: asteroid-v3-app-command-guideline
description: Use when changing Asteroid_V3 slash commands, app_commands groups, context menus, setup commands, persistent views, buttons, selects, modals, permissions, guild scope checks, ephemeral responses, embeds, Layout / Components V2 responses, names, or command audit logs.
---

# Asteroid V3 App Command Guideline

Treat permissions, response visibility, UI callback authorization, and audit logs as command contract.

## Entry Points

Start from:

- `app/common/command_groups.py`: command/group/setup registration.
- `app/common/guild_scope.py`: operating-guild checks for commands and UI.
- `app/common/permissions.py`: `ADMINISTRATOR_PERMISSIONS`, `admin_only`.
- `app/common/discord_types.py`: Discord.py narrowing.
- `app/features/*/{cog.py,commands/*.py,views*.py}` and related tests.

Use `rg -n "@app_commands\\.command|\\.command\\(|app_commands\\.Group|discord\\.ui|register_setup_command|register_command|register_group" app tests`.

## Classification

Classify each entry point:

- Admin-only: changes others' data, roles, channels, punishments, reports, ranking, XP, shards, power, setup posts, persistent messages, imports, migrations, or config-like state.
- Scoped management: actor owns or can manage the concrete resource.
- Daily use: read-only, self-service, or low-risk actor-only action.

## Permission Rules

- Keep all commands restricted by `OperatingGuildCommandTree`; do not bypass the global operating-guild check.
- Derive every View and Modal from `GuildScopedView` or `GuildScopedModal`, including temporary and paginator UI.
- Treat DM and interactions outside `config.discord.guild_id` as unavailable; reject them ephemerally with the shared message.
- Admin top-level groups: `default_permissions=ADMINISTRATOR_PERMISSIONS`, `guild_only=True`.
- Admin commands: `@admin_only`.
- One-time admin setup: prefer `register_setup_command`; shared `/setup` is admin-default.
- Admin subcommands under public groups need runtime checks.
- Scoped commands must check the target resource and actor relationship.
- Button/Select/Modal callbacks must authorize inside the callback; slash checks do not protect UI callbacks.
- Never rely only on channel/message location or `custom_id`.

## Response Style

- Prefer Embed or Layout / Components V2 responses unless nearby code or Discord constraints favor plain text.
- Use Layout / Components V2 actively when the response has high information density, repeated sections, mixed controls and content, persistent panels, or presentation that benefits from `Container`, `Section`, `TextDisplay`, `Separator`, media, or component grouping.
- Use Embed for simple notifications, concise status messages, and ordinary structured command results where Components V2 would add only layout overhead.
- Use ephemeral for setup feedback, validation errors, denials, self-service results, and private details.
- Use public responses for naturally visible workflow results.
- State-changing admin actions also need structured logs; ephemeral replies are not audit trails.

## Naming And Descriptions

- Command/subcommand names: English.
- Public argument names: Japanese. Keep Python identifiers readable; use `@app_commands.rename(...)` when public names differ.
- Command and argument descriptions: Japanese.
- Keep names short, stable, and Discord-compatible.

## Audit Logging

Use `asteroid-v3-logging-guideline` for levels. For command mutations, log what changed with stable IDs: `command`, `guild_id`, `channel_id`, actor/user ID, target IDs, and details such as `amount`, `old_*`, `new_*`, `enabled`, or `reason`.

Never log secrets, private report bodies outside the intended moderation workflow, large payloads, embeds, or raw Discord objects.

## Tests

Add focused tests when command visibility, guild scope, runtime checks, setup registration, or UI callback authorization changes. Start from `tests/test_guild_scope.py`, `tests/test_command_permissions.py`, and `tests/test_command_groups.py`.
