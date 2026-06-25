---
name: asteroid-v3-test-guideline
description: Use when adding, changing, reorganizing, or diagnosing Asteroid_V3 tests, including pytest, Given-When-Then style, Japanese docstring specs, fake Discord objects, feature tests, repository tests, command permission tests, guild-scope tests, setup registration tests, config tests, caplog, or verification strategy.
---

# Asteroid V3 Test Guideline

Use tests to lock functional and non-functional requirements at the smallest useful boundary first, then broaden verification when shared behavior is touched.

For the team-facing test plan, read `tests/README.md` first.

## Test Layout

- Place feature-specific tests under `tests/features/<feature>/`.
- Place cross-feature contracts under `tests/common/`.
- Place bot startup, config, extension loading, and system command tests under `tests/core/`.
- Place repository and migration tests under `tests/database/`.
- Place shared fakes, factories, and assertions under `tests/support/`.
- Do not split tests by `unit` / `integration` / `e2e` directories by default.
- Split test files by what functional or non-functional requirement you want to test. Production responsibility is a placement hint, not the final reason.
- Read the code intent first. Test that the functional requirement is satisfied; when a non-functional requirement is visible, test that property too.
- If no meaningful non-functional requirement exists for the behavior, do not invent one and do not add a `# 非機能要件：...` comment.
- Do not create placeholder test files for every category. Add only files that match the contracts being protected.
- Treat `tests_archive/` as old-test storage, not as the source of truth for new tests.

## Test Style

- Write test bodies with Given-When-Then comments.
- Before Given-When-Then, add Japanese comments that explicitly identify the tested requirement: `# 機能要件：...` and/or `# 非機能要件：...`.
- Use `# 機能要件：...` for externally visible behavior such as commands, UI responses, service results, repository results, and config behavior.
- Use `# 非機能要件：...` for properties such as authorization, guild scope, side-effect prevention, idempotency, logging, error handling, and stability.
- Do not force a non-functional requirement comment when no non-functional requirement exists or is being tested.
- Keep test function names short and English.
- Put the detailed behavior description in a Japanese function docstring.
- Make the docstring describe the externally visible contract, not private implementation details.

Example:

```python
async def test_rejects_outside_guild(fake_interaction, service):
    """対象外 guild の UI 操作では拒否応答のみを返し、ロール更新は行わない。"""
    # 機能要件：対象外 guild の UI 操作は拒否応答を返す。
    # 非機能要件：拒否された操作ではロール更新などの副作用を発生させない。
    # Given
    fake_interaction.guild_id = 999

    # When
    await service.handle(fake_interaction)

    # Then
    assert fake_interaction.response.ephemeral is True
    assert service.updated_roles == []
```

## What To Test

- Read the code intent first, name the functional requirement that must be satisfied, then choose the file that makes that contract easiest to understand.
- If the code exposes a meaningful non-functional requirement, name it and test it explicitly.
- If the code does not expose a meaningful non-functional requirement, record only the functional requirement in the test comments.
- Pure domain functions and calculations directly.
- Services with fake Discord objects when behavior does not require real Discord API calls.
- Repository create/update/delete/list behavior when DB persistence changes.
- Command registration helpers and permission metadata for command visibility changes.
- Runtime permission checks for admin, scoped management, and UI callbacks.
- Config parsing when config schema or defaults change.
- Logging behavior with `caplog` when log level or audit content is part of the contract.

## Test Case Design

- Use equivalence partitioning to choose representative valid/invalid inputs and states instead of adding many redundant cases.
- Use boundary value analysis for thresholds, counts, lengths, dates, cooldowns, grade/rank ranges, and permission limits. Include the boundary and adjacent rejected values when they define the contract.
- Use decision tables when multiple conditions affect the result, such as guild scope, permissions, feature flags, target validity, and current state.
- Use state-transition tests for registration/update/delete/restore/offline/panel-refresh flows.
- Use error guessing for known risky paths: outside guild, DM, permission denial, missing rows, unknown config keys, Discord API boundaries, and DB boundaries.
- For rejection tests, assert both the rejection response and the absence of side effects such as DB writes, role changes, sends, or cache updates.

## Feature Test Files

- Use `test_service.py` when you want to test feature-level state decisions, service contracts, or repository/Discord orchestration.
- Use `test_commands.py` when you want to test slash command public API, command groups, public argument names, permissions, responses, or audit logs.
- Use `test_views.py` when you want to test Button, Select, Modal, or View callback authorization and side effects.
- Use `test_runtime.py` when you want to test listeners, scheduled tasks, startup hooks, or cog lifecycle behavior.
- Use `test_domain.py` when you want to test pure calculations, policy decisions, normalization, or value objects.
- Put repository tests in `tests/database/repositories/`, not under the feature directory.
- Put config and extension tests in `tests/core/`, not under the feature directory.
- Do not add `test_panel.py` mechanically. Persistent panel lifecycle belongs to `tests/common/test_persistent_panels.py`; add feature panel tests only when feature-specific panel rendering or behavior cannot be covered clearly through service/view tests.

## Fake Discord Objects

- Use small fake objects that expose only the attributes needed by the behavior under test.
- Use `typing.cast` at the test boundary when a fake object intentionally stands in for a Discord.py type.
- Do not weaken production type guards or authorization checks to make fake objects pass.
- Prefer extracting pure logic from Cog/View code when fake setup becomes too complex.

## Command Tests

- Check commands, Views, and Modals allow `config.discord.guild_id` and reject other guilds and DMs before callbacks mutate state.
- Check guild event listeners and scheduled tasks do not call services, update DB state, cache messages, or send to channels outside the operating guild.
- Start shared guild-scope coverage from `tests/common/test_guild_scope.py`.
- Check `guild_only`, `default_permissions`, and command checks for admin command groups.
- Check setup commands register under the shared `/setup` group through `register_setup_command`.
- Check public groups with admin subcommands still have runtime checks.
- Add feature-specific tests for UI callback authorization when callbacks mutate state.

## Scope And Verification

- Run the narrow relevant tests first while iterating.
- Run broader tests when touching shared helpers, config, database infrastructure, command registration, or permission logic.
- Use `mise run check` for final broad verification when practical.
