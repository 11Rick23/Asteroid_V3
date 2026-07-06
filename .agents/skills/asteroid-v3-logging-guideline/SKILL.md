---
name: asteroid-v3-logging-guideline
description: Use when adding, changing, reviewing, or testing Asteroid_V3 logger.debug/info/warning/error/exception calls, audit logs, command logs, UI callback logs, service logs, or feature behavior logs.
---

# Asteroid V3 Logging Guideline

Classify logs by operational meaning, then severity. Prefer logs that say what happened, who triggered it, and what state changed.

Also use `asteroid-v3-app-command-guideline` for command/UI mutations of DB rows, roles, channels, moderation, setup messages, ranking, XP, shards, power, starboard, VC, birthday, auth, reports, suggestions, or other user/server state.

## Level Rules

- `logger.debug`: ordinary user flow, expected denial, validation failure, no-op, already-done state, noisy repeated event, or debug-only detail.
- `logger.info`: admin/moderator action, setup change, maintenance, persistent message creation/deletion/recreation, import, migration, manual refresh, or other low-frequency operational action.
- `logger.warning`: foreseeable abnormal state needing attention, such as missing configured objects, stale UI state, deleted target records, permission hierarchy mismatch, inconsistent DB/config/runtime state, unreachable denial, recoverable Discord API failure, or suspicious input.
- `logger.error`: serious feature failure where traceback is not needed or unavailable.
- `logger.exception`: unexpected exception inside `except` where traceback is useful.

## Message Content

Log stable facts, not private content. Include available `command`, `guild_id`, `channel_id`, actor/user ID, target IDs, and mutation details such as `amount`, `type`, `count`, `old_*`, `new_*`, `enabled`, or `reason`.

Do not log tokens, DB URLs, passwords, API keys, secrets, sensitive user text outside intended moderation workflows, large payloads, embeds, or raw Discord objects.

## Review Workflow

1. Identify whether the event is ordinary user flow, admin/operation flow, foreseeable abnormal state, or unexpected failure.
2. Choose the lowest level that still preserves operational value.
3. For mutations, log what changed rather than only that a command ran.
4. For warnings and errors, include enough IDs to investigate and reproduce.
5. Keep tests aligned when they assert log level or log text.
