---
name: asteroid-v3-test-guideline
description: Use when adding, changing, or diagnosing Asteroid_V3 tests, including pytest, pytest-asyncio, fake Discord objects, service tests, repository tests, command permission and guild scope tests, setup registration tests, config tests, caplog, or verification strategy.
---

# Asteroid V3 Test Guideline

Use tests to lock the contract at the smallest useful boundary first, then broaden verification when shared behavior is touched.

## What To Test

- Pure domain functions and calculations directly.
- Services with fake Discord objects when behavior does not require real Discord API calls.
- Repository create/update/delete/list behavior when DB persistence changes.
- Command registration helpers and permission metadata for command visibility changes.
- Runtime permission checks for admin, scoped management, and UI callbacks.
- Config parsing when config schema or defaults change.
- Logging behavior with `caplog` when log level or audit content is part of the contract.

## Fake Discord Objects

- Use small fake objects that expose only the attributes needed by the behavior under test.
- Use `typing.cast` at the test boundary when a fake object intentionally stands in for a Discord.py type.
- Do not weaken production type guards or authorization checks to make fake objects pass.
- Prefer extracting pure logic from Cog/View code when fake setup becomes too complex.

## Command Tests

- Check commands, Views, and Modals allow `config.discord.guild_id` and reject other guilds and DMs before callbacks mutate state.
- Check guild event listeners and scheduled tasks do not call services, update DB state, cache messages, or send to channels outside the operating guild.
- Start shared guild-scope coverage from `tests/test_guild_scope.py`.
- Check `guild_only`, `default_permissions`, and command checks for admin command groups.
- Check setup commands register under the shared `/setup` group through `register_setup_command`.
- Check public groups with admin subcommands still have runtime checks.
- Add feature-specific tests for UI callback authorization when callbacks mutate state.

## Scope And Verification

- Run the narrow relevant tests first while iterating.
- Run broader tests when touching shared helpers, config, database infrastructure, command registration, or permission logic.
- Use `mise run check` for final broad verification when practical.
